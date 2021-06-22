# coding=utf-8
# Copyright 2021 NVIDIA The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" PyTorch SegFormer model. """

import math
import os
import collections

import torch
import torch.utils.checkpoint
from torch import nn
from torch.nn import CrossEntropyLoss, MSELoss

from ...activations import ACT2FN
from ...file_utils import (
    add_code_sample_docstrings,
    add_start_docstrings,
    add_start_docstrings_to_model_forward,
    replace_return_docstrings,
)
from ...modeling_outputs import (
    BaseModelOutput,
)
from ...modeling_utils import (
    PreTrainedModel,
    SequenceSummary,
    apply_chunking_to_forward,
    find_pruneable_heads_and_indices,
    prune_linear_layer,
)
from ...utils import logging
from .configuration_segformer import SegFormerConfig


logger = logging.get_logger(__name__)

_CHECKPOINT_FOR_DOC = "nvidia/segformer-b0"
_CONFIG_FOR_DOC = "SegFormerConfig"

SEGFORMER_PRETRAINED_MODEL_ARCHIVE_LIST = [
    "nvidia/segformer-b0",
    # See all SegFormer models at https://huggingface.co/models?filter=segformer
]

# Inspired by
# https://github.com/rwightman/pytorch-image-models/blob/b9bd960a032c75ca6b808ddeed76bee5f3ed4972/timm/models/layers/helpers.py
# From PyTorch internals
def to_2tuple(x):
    if isinstance(x, collections.abc.Iterable):
        return x
    return (x, x)


# Stochastic depth implementation
# Inspired by https://github.com/rwightman/pytorch-image-models/blob/master/timm/models/layers/drop.py
def drop_path(x, drop_prob: float = 0., training: bool = False):
    """Drop paths (Stochastic Depth) per sample (when applied in main path of residual blocks).
    This is the same as the DropConnect impl I created for EfficientNet, etc networks, however,
    the original name is misleading as 'Drop Connect' is a different form of dropout in a separate paper...
    See discussion: https://github.com/tensorflow/tpu/issues/494#issuecomment-532968956 ... I've opted for
    changing the layer and argument names to 'drop path' rather than mix DropConnect as a layer name and use
    'survival rate' as the argument.
    """
    if drop_prob == 0. or not training:
        return x
    keep_prob = 1 - drop_prob
    shape = (x.shape[0],) + (1,) * (x.ndim - 1)  # work with diff dim tensors, not just 2D ConvNets
    random_tensor = keep_prob + torch.rand(shape, dtype=x.dtype, device=x.device)
    random_tensor.floor_()  # binarize
    output = x.div(keep_prob) * random_tensor
    return output


class DropPath(nn.Module):
    """Drop paths (Stochastic Depth) per sample  (when applied in main path of residual blocks).
    """
    def __init__(self, drop_prob=None):
        super(DropPath, self).__init__()
        self.drop_prob = drop_prob

    def forward(self, x):
        return drop_path(x, self.drop_prob, self.training)


SEGFORMER_START_DOCSTRING = r"""
    This model inherits from :class:`~transformers.PreTrainedModel`. Check the superclass documentation for the generic
    methods the library implements for all its model (such as downloading or saving, resizing the input embeddings,
    pruning heads etc.)
    This model is also a PyTorch `torch.nn.Module <https://pytorch.org/docs/stable/nn.html#torch.nn.Module>`__
    subclass. Use it as a regular PyTorch Module and refer to the PyTorch documentation for all matter related to
    general usage and behavior.
    Parameters:
        config (:class:`~transformers.SegFormerConfig`):
            Model configuration class with all the parameters of the model. Initializing with a config file does not
            load the weights associated with the model, only the configuration. Check out the
            :meth:`~transformers.PreTrainedModel.from_pretrained` method to load the model weights.
"""

SEGFORMER_INPUTS_DOCSTRING = r"""
    Args:
        pixel_values (:obj:`torch.FloatTensor` of shape :obj:`(batch_size, num_channels, height, width)`):
            Pixel values. Padding will be ignored by default should you provide it.
            Pixel values can be obtained using :class:`~transformers.DetrTokenizer`. See
            :meth:`transformers.DetrTokenizer.__call__` for details.
        output_attentions (:obj:`bool`, `optional`):
            Whether or not to return the attentions tensors of all attention layers. See ``attentions`` under returned
            tensors for more detail.
        output_hidden_states (:obj:`bool`, `optional`):
            Whether or not to return the hidden states of all layers. See ``hidden_states`` under returned tensors for
            more detail.
        return_dict (:obj:`bool`, `optional`):
            Whether or not to return a :class:`~transformers.file_utils.ModelOutput` instead of a plain tuple.
"""


class SegFormerPreTrainedModel(PreTrainedModel):
    config_class = SegFormerConfig
    base_model_prefix = "model"

    def _init_weights(self, module):
        std = self.config.init_std

        if isinstance(module, (nn.Linear, nn.Conv2d)):
            # Slightly different from the TF version which uses truncated_normal for initialization
            # cf https://github.com/pytorch/pytorch/pull/5617
            module.weight.data.normal_(mean=0.0, std=std)
            if module.bias is not None:
                module.bias.data.zero_()
        elif isinstance(module, nn.Embedding):
            module.weight.data.normal_(mean=0.0, std=std)
            if module.padding_idx is not None:
                module.weight.data[module.padding_idx].zero_()


class SegFormerOverlapPatchEmbeddings(nn.Module):
    """Construct the patch embeddings from an image."""

    def __init__(self, image_size, patch_size, stride, num_channels, hidden_size):
        super().__init__()
        image_size = to_2tuple(image_size)
        patch_size = to_2tuple(patch_size)
        self.height, self.width = image_size[0] // patch_size[0], image_size[1] // patch_size[1]
        self.num_patches = self.height * self.width
        self.proj = nn.Conv2d(num_channels, hidden_size, kernel_size=patch_size, stride=stride,
                              padding=(patch_size[0] // 2, patch_size[1] // 2))

        self.layer_norm = nn.LayerNorm(hidden_size)

    def forward(self, pixel_values):

        x = self.proj(pixel_values)
        _, _, height, width = x.shape
        x = x.flatten(2).transpose(1, 2)
        x = self.layer_norm(x)
        return x, height, width


class SegFormerEfficientSelfAttention(nn.Module):
    def __init__(self, config, hidden_size, num_attention_heads, sr_ratio):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_attention_heads = num_attention_heads

        if self.hidden_size % self.num_attention_heads != 0:
            raise ValueError(
                f"The hidden size ({self.hidden_size}) is not a multiple of the number of attention "
                f"heads ({self.num_attention_heads})"
            )

        self.attention_head_size = int(self.hidden_size / self.num_attention_heads)
        self.all_head_size = self.num_attention_heads * self.attention_head_size

        self.query = nn.Linear(self.hidden_size, self.all_head_size)
        self.key = nn.Linear(self.hidden_size, self.all_head_size)
        self.value = nn.Linear(self.hidden_size, self.all_head_size)

        self.dropout = nn.Dropout(config.attention_dropout)

        self.sr_ratio = sr_ratio
        if sr_ratio > 1:
            self.sr = nn.Conv2d(hidden_size, hidden_size, kernel_size=sr_ratio, stride=sr_ratio)
            self.layer_norm = nn.LayerNorm(hidden_size)

    def transpose_for_scores(self, x):
        new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
        x = x.view(*new_x_shape)
        return x.permute(0, 2, 1, 3)

    def forward(
        self,
        hidden_states,
        height,
        width,
        attention_mask=None,
        head_mask=None,
        output_attentions=False,
    ):
        query_layer = self.transpose_for_scores(self.query(hidden_states))

        if self.sr_ratio > 1:
            batch_size, seq_len, num_channels = hidden_states.shape
            hidden_states = hidden_states.permute(0, 2, 1).reshape(batch_size, num_channels, height, width)
            hidden_states = self.sr(hidden_states).reshape(batch_size, num_channels, -1).permute(0, 2, 1)
            hidden_states = self.layer_norm(hidden_states)
        
        key_layer = self.transpose_for_scores(self.key(hidden_states))
        value_layer = self.transpose_for_scores(self.value(hidden_states))

        # Take the dot product between "query" and "key" to get the raw attention scores.
        attention_scores = torch.matmul(query_layer, key_layer.transpose(-1, -2))

        attention_scores = attention_scores / math.sqrt(self.attention_head_size)

        # Normalize the attention scores to probabilities.
        attention_probs = nn.Softmax(dim=-1)(attention_scores)

        # This is actually dropping out entire tokens to attend to, which might
        # seem a bit unusual, but is taken from the original Transformer paper.
        attention_probs = self.dropout(attention_probs)

        # Mask heads if we want to
        if head_mask is not None:
            attention_probs = attention_probs * head_mask

        context_layer = torch.matmul(attention_probs, value_layer)

        context_layer = context_layer.permute(0, 2, 1, 3).contiguous()
        new_context_layer_shape = context_layer.size()[:-2] + (self.all_head_size,)
        context_layer = context_layer.view(*new_context_layer_shape)

        outputs = (context_layer, attention_probs) if output_attentions else (context_layer,)

        return outputs


# class SegFormerSelfOutput(nn.Module):
#     def __init__(self, config, hidden_size):
#         super().__init__()
#         self.dense = nn.Linear(hidden_size, hidden_size)
#         self.LayerNorm = nn.LayerNorm(hidden_size, eps=config.layer_norm_eps)
#         self.dropout = nn.Dropout(config.dropout)

#     def forward(self, hidden_states, input_tensor):
#         hidden_states = self.dense(hidden_states)
#         hidden_states = self.dropout(hidden_states)
#         hidden_states = self.LayerNorm(hidden_states + input_tensor)
#         return hidden_states


class SegFormerAttention(nn.Module):
    def __init__(self, config, hidden_size, num_attention_heads, sr_ratio):
        super().__init__()
        self.self = SegFormerEfficientSelfAttention(config=config, hidden_size=hidden_size, num_attention_heads=num_attention_heads, 
                                                     sr_ratio=sr_ratio)
        self.pruned_heads = set()

    def prune_heads(self, heads):
        if len(heads) == 0:
            return
        heads, index = find_pruneable_heads_and_indices(
            heads, self.self.num_attention_heads, self.self.attention_head_size, self.pruned_heads
        )

        # Prune linear layers
        self.self.query = prune_linear_layer(self.self.query, index)
        self.self.key = prune_linear_layer(self.self.key, index)
        self.self.value = prune_linear_layer(self.self.value, index)
        self.output.dense = prune_linear_layer(self.output.dense, index, dim=1)

        # Update hyper params and store pruned heads
        self.self.num_attention_heads = self.self.num_attention_heads - len(heads)
        self.self.all_head_size = self.self.attention_head_size * self.self.num_attention_heads
        self.pruned_heads = self.pruned_heads.union(heads)

    def forward(
        self,
        hidden_states,
        height,
        width,
        head_mask=None,
        output_attentions=False,
    ):
        self_outputs = self.self(
            hidden_states,
            height,
            width,
            head_mask,
            output_attentions,
        )

        #attention_output = self.output(self_outputs[0], hidden_states)
        attention_output = self_outputs[0]
        outputs = (attention_output,) + self_outputs[1:]  # add attentions if we output them
        return outputs


class SegFormerDWConv(nn.Module):
    def __init__(self, dim=768):
        super(SegFormerDWConv, self).__init__()
        self.dwconv = nn.Conv2d(dim, dim, 3, 1, 1, bias=True, groups=dim)

    def forward(self, hidden_states, height, width):
        batch_size, seq_len, num_channels = hidden_states.shape
        hidden_states = hidden_states.transpose(1, 2).view(batch_size, num_channels, height, width)
        hidden_states = self.dwconv(hidden_states)
        hidden_states = hidden_states.flatten(2).transpose(1, 2)

        return hidden_states


class SegFormerMixFFN(nn.Module):
    def __init__(self, config, in_features, hidden_features=None, out_features=None):
        super().__init__()
        out_features = out_features or in_features
        self.dense1 = nn.Linear(in_features, hidden_features)
        self.dwconv = SegFormerDWConv(hidden_features)
        if isinstance(config.activation_function, str):
            self.intermediate_act_fn = ACT2FN[config.activation_function]
        else:
            self.intermediate_act_fn = config.activation_function
        self.dense2 = nn.Linear(hidden_features, out_features)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, hidden_states, height, width):
        hidden_states = self.dense1(hidden_states)
        hidden_states = self.dwconv(hidden_states, height, width)
        hidden_states = self.intermediate_act_fn(hidden_states)
        hidden_states = self.dropout(hidden_states)
        hidden_states = self.dense2(hidden_states)
        hidden_states = self.dropout(hidden_states)
        return hidden_states


class SegFormerEncoderLayer(nn.Module):
    """This corresponds to the Block class in the original implementation."""
    
    def __init__(self, config, hidden_size, num_attention_heads, drop_path, sr_ratio, mlp_ratio):
        super().__init__()
        self.layer_norm_1 = nn.LayerNorm(hidden_size)
        self.attention = SegFormerAttention(config, hidden_size=hidden_size, num_attention_heads=num_attention_heads, sr_ratio=sr_ratio)
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()
        self.layer_norm_2 = nn.LayerNorm(hidden_size)
        mlp_hidden_size = int(hidden_size * mlp_ratio)
        self.mlp = SegFormerMixFFN(config, in_features=hidden_size, hidden_features=mlp_hidden_size)

    def forward(
        self,
        hidden_states,
        height,
        width,
        head_mask=None,
        output_attentions=False,
    ):
        self_attention_outputs = self.attention(
            self.layer_norm_1(hidden_states), # in SegFormer, layernorm is applied before self-attention
            height,
            width,
            head_mask,
            output_attentions=output_attentions,
        )
        attention_output = self_attention_outputs[0]
        outputs = self_attention_outputs[1:]  # add self attentions if we output attention weights

        # first residual connection (with stochastic depth)
        attention_output = self.drop_path(attention_output)
        hidden_states = attention_output + hidden_states 

        mlp_output = self.mlp(self.layer_norm_2(hidden_states), height, width)
        
        # second residual connection (with stochastic depth)
        mlp_output = self.drop_path(mlp_output)
        layer_output = mlp_output + hidden_states 

        outputs = (layer_output,) + outputs
        
        return outputs


class SegFormerEncoder(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        dpr = [x.item() for x in torch.linspace(0, config.drop_path_rate, sum(config.depths))]  # stochastic depth decay rule

        # patch embeddings
        embeddings = []
        for i in range(config.num_encoder_blocks):
            embeddings.append(SegFormerOverlapPatchEmbeddings(image_size=config.image_size // config.downsampling_rates[i], 
                                             patch_size=config.patch_sizes[i], stride=config.strides[i], 
                                             num_channels=config.hidden_sizes[i-1] if i != 0 else config.num_channels, 
                                             hidden_size=config.hidden_sizes[i]))
        self.patch_embeddings = nn.ModuleList(embeddings)

        # Transformer blocks
        blocks = []
        cur = 0
        for i in range(config.num_encoder_blocks):
            # each block consists of layers
            layers = []
            if i != 0:
                cur += config.depths[i-1]
            for j in range(config.depths[i]):
                layers.append(SegFormerEncoderLayer(config, hidden_size=config.hidden_sizes[i], num_attention_heads=config.encoder_attention_heads[i],
                                                   drop_path=dpr[cur + j], sr_ratio=config.sr_ratios[i], mlp_ratio=config.mlp_ratio[i]))
            blocks.append(nn.ModuleList(layers))
        
        self.block = nn.ModuleList(blocks)
            
        # Layer norms
        self.layer_norm = nn.ModuleList([nn.LayerNorm(config.hidden_sizes[i]) for i in range(config.num_encoder_blocks)])

    def forward(
        self,
        pixel_values,
        head_mask=None,
        output_attentions=False,
        output_hidden_states=False,
        return_dict=True,
    ):
        all_hidden_states = () if output_hidden_states else None
        all_self_attentions = () if output_attentions else None

        batch_size = pixel_values.shape[0]
        
        features = []
        hidden_states = pixel_values
        for embedding_layer, block_layer, norm_layer in zip(self.patch_embeddings, self.block, self.layer_norm):
            # first, obtain patch embeddings
            hidden_states, height, width = embedding_layer(hidden_states)
            # second, send embeddings through blocks
            for i, blk in enumerate(block_layer):
                layer_outputs = blk(hidden_states, height, width)
                hidden_states = layer_outputs[0]
            # third, apply layer norm and reshape
            hidden_states = norm_layer(hidden_states)
            hidden_states = hidden_states.reshape(batch_size, height, width, -1).permute(0, 3, 1, 2).contiguous()
            features.append(hidden_states)
        
        # for i, layer_module in enumerate(self.layer):
        #     if output_hidden_states:
        #         all_hidden_states = all_hidden_states + (hidden_states,)

        #     layer_head_mask = head_mask[i] if head_mask is not None else None

        #     if getattr(self.config, "gradient_checkpointing", False) and self.training:

        #         def create_custom_forward(module):
        #             def custom_forward(*inputs):
        #                 return module(*inputs, output_attentions)

        #             return custom_forward

        #         layer_outputs = torch.utils.checkpoint.checkpoint(
        #             create_custom_forward(layer_module),
        #             hidden_states,
        #             attention_mask,
        #             layer_head_mask,
        #         )
        #     else:
        #         layer_outputs = layer_module(
        #             hidden_states,
        #             attention_mask,
        #             layer_head_mask,
        #             output_attentions,
        #         )

        #     hidden_states = layer_outputs[0]
        #     if output_attentions:
        #         all_self_attentions = all_self_attentions + (layer_outputs[1],)

        # if output_hidden_states:
        #     all_hidden_states = all_hidden_states + (hidden_states,)

        if not return_dict:
            return tuple(
                v
                for v in [
                    hidden_states,
                    all_hidden_states,
                    all_self_attentions,
                ]
                if v is not None
            )
        return BaseModelOutput(
            last_hidden_state=hidden_states,
            hidden_states=all_hidden_states,
            attentions=all_self_attentions,
        )


class SegFormerDecoderLayer(nn.Module):
    """
    Linear Embedding.
    """
    
    def __init__(self, config: SegFormerConfig, input_dim):
        super().__init__()
        self.proj = nn.Linear(input_dim, config.decoder_hidden_size)

    def forward(self, hidden_states: torch.Tensor):
        hidden_states = hidden_states.flatten(2).transpose(1, 2)
        hidden_states = self.proj(hidden_states)
        return hidden_states


class SegFormerDecoder(SegFormerPreTrainedModel):
    """
    All-MLP decoder consisting of *config.decoder_layers* layers. Each layer is a :class:`SegFormerDecoderLayer`.

    Args:
        config: SegFormerConfig
    """

    def __init__(self, config: SegFormerConfig):
        super().__init__(config)

        assert len(config.feature_strides) == len(config.in_channels)
        assert min(config.feature_strides) == config.feature_strides[0]
        
        mlps = []
        for i in reversed(range(config.decoder_layers)):
            mlps.append(SegFormerDecoderLayer(config, input_dim=config.in_channels[i]))

        self.linear_c = nn.ModuleList(mlps)
        
        self.linear_fuse = nn.Conv2d(in_channels=config.decoder_hidden_size*4, out_channels=config.decoder_hidden_size, kernel_size=1)
        self.batch_norm = nn.BatchNorm2d(config.decoder_hidden_size)

        self.dropout = nn.Dropout(config.dropout)

        self.init_weights()

    def forward(
        self,
        features,
        output_hidden_states=None,
        return_dict=None,
    ):
        r"""
        Args:
            features (:obj:`List[torch.FloatTensor]` of shape :obj:`(batch_size, sequence_length, hidden_size)`, `optional`):
                ...
            output_hidden_states (:obj:`bool`, `optional`):
                Whether or not to return the hidden states of all layers. See ``hidden_states`` under returned tensors
                for more detail.
            return_dict (:obj:`bool`, `optional`):
                Whether or not to return a :class:`~transformers.file_utils.ModelOutput` instead of a plain tuple.
        """
        output_hidden_states = (
            output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
        )
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        # decoder layers
        all_hidden_states = () if output_hidden_states else None
        
        for idx, decoder_layer in enumerate(self.layers):
            if output_hidden_states:
                all_hidden_states += (hidden_states,)

            layer_outputs = decoder_layer(
                hidden_states
            )
            hidden_states = layer_outputs[0]

        # add hidden states from the last decoder layer
        if output_hidden_states:
            all_hidden_states += (hidden_states,)

        if not return_dict:
            return tuple(
                v
                for v in [hidden_states, all_hidden_states]
                if v is not None
            )
        return BaseModelOutput(
            last_hidden_state=hidden_states,
            hidden_states=all_hidden_states,
        )


@add_start_docstrings(
    "The bare SegFormer encoder-decoder model outputting raw hidden-states without any specific head on top.",
    SEGFORMER_START_DOCSTRING,
)
class SegFormerModel(SegFormerPreTrainedModel):
    def __init__(self, config: SegFormerConfig):
        super().__init__(config)

        # hierarchical Transformer encoder
        self.encoder = SegFormerEncoder(config)
        # all-MLP decoder
        #self.decoder = SegFormerDecoder(config)

        self.init_weights()

    def get_encoder(self):
        return self.encoder

    # def get_decoder(self):
    #     return self.decoder

    @add_start_docstrings_to_model_forward(SEGFORMER_INPUTS_DOCSTRING)
    def forward(
        self,
        pixel_values,
        head_mask=None,
        encoder_outputs=None,
        inputs_embeds=None,
        decoder_inputs_embeds=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
    ):
        output_attentions = output_attentions if output_attentions is not None else self.config.output_attentions
        output_hidden_states = (
            output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
        )
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict
        
        if encoder_outputs is None:
            encoder_outputs = self.encoder(
                pixel_values,
                output_attentions=output_attentions,
                output_hidden_states=output_hidden_states,
                return_dict=return_dict,
            )
        # If the user passed a tuple for encoder_outputs, we wrap it in a BaseModelOutput when return_dict=True
        elif return_dict and not isinstance(encoder_outputs, BaseModelOutput):
            encoder_outputs = BaseModelOutput(
                last_hidden_state=encoder_outputs[0],
                hidden_states=encoder_outputs[1] if len(encoder_outputs) > 1 else None,
                attentions=encoder_outputs[2] if len(encoder_outputs) > 2 else None,
            )

        # decoder outputs consists of (dec_features, dec_hidden, dec_attn)
        # decoder_outputs = self.decoder(
        #     input_ids=decoder_input_ids,
        #     attention_mask=decoder_attention_mask,
        #     encoder_hidden_states=encoder_outputs[0],
        #     encoder_attention_mask=attention_mask,
        #     head_mask=decoder_head_mask,
        #     inputs_embeds=decoder_inputs_embeds,
        #     output_attentions=output_attentions,
        #     output_hidden_states=output_hidden_states,
        #     return_dict=return_dict,
        # )

        # if not return_dict:
        #     return decoder_outputs + encoder_outputs

        # return Seq2SeqModelOutput(
        #     last_hidden_state=decoder_outputs.last_hidden_state,
        #     decoder_hidden_states=decoder_outputs.hidden_states,
        #     decoder_attentions=decoder_outputs.attentions,
        #     encoder_last_hidden_state=encoder_outputs.last_hidden_state,
        #     encoder_hidden_states=encoder_outputs.hidden_states,
        #     encoder_attentions=encoder_outputs.attentions,
        # )

        return encoder_outputs