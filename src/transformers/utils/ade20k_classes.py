# ADE20k id's to class names
# note: ADE20k is actually a way bigger dataset, the classes below are defined 
# in the so-called MIT Scene Parsing Benchmark (SceneParse150)
# see http://sceneparsing.csail.mit.edu/
id2label = {
 0: 'wall',
 1: 'building',
 2: 'sky',
 3: 'floor',
 4: 'tree',
 5: 'ceiling',
 6: 'road',
 7: 'bed ',
 8: 'windowpane',
 9: 'grass',
 10: 'cabinet',
 11: 'sidewalk',
 12: 'person',
 13: 'earth',
 14: 'door',
 15: 'table',
 16: 'mountain',
 17: 'plant',
 18: 'curtain',
 19: 'chair',
 20: 'car',
 21: 'water',
 22: 'painting',
 23: 'sofa',
 24: 'shelf',
 25: 'house',
 26: 'sea',
 27: 'mirror',
 28: 'rug',
 29: 'field',
 30: 'armchair',
 31: 'seat',
 32: 'fence',
 33: 'desk',
 34: 'rock',
 35: 'wardrobe',
 36: 'lamp',
 37: 'bathtub',
 38: 'railing',
 39: 'cushion',
 40: 'base',
 41: 'box',
 42: 'column',
 43: 'signboard',
 44: 'chest of drawers',
 45: 'counter',
 46: 'sand',
 47: 'sink',
 48: 'skyscraper',
 49: 'fireplace',
 50: 'refrigerator',
 51: 'grandstand',
 52: 'path',
 53: 'stairs',
 54: 'runway',
 55: 'case',
 56: 'pool table',
 57: 'pillow',
 58: 'screen door',
 59: 'stairway',
 60: 'river',
 61: 'bridge',
 62: 'bookcase',
 63: 'blind',
 64: 'coffee table',
 65: 'toilet',
 66: 'flower',
 67: 'book',
 68: 'hill',
 69: 'bench',
 70: 'countertop',
 71: 'stove',
 72: 'palm',
 73: 'kitchen island',
 74: 'computer',
 75: 'swivel chair',
 76: 'boat',
 77: 'bar',
 78: 'arcade machine',
 79: 'hovel',
 80: 'bus',
 81: 'towel',
 82: 'light',
 83: 'truck',
 84: 'tower',
 85: 'chandelier',
 86: 'awning',
 87: 'streetlight',
 88: 'booth',
 89: 'television receiver',
 90: 'airplane',
 91: 'dirt track',
 92: 'apparel',
 93: 'pole',
 94: 'land',
 95: 'bannister',
 96: 'escalator',
 97: 'ottoman',
 98: 'bottle',
 99: 'buffet',
 100: 'poster',
 101: 'stage',
 102: 'van',
 103: 'ship',
 104: 'fountain',
 105: 'conveyer belt',
 106: 'canopy',
 107: 'washer',
 108: 'plaything',
 109: 'swimming pool',
 110: 'stool',
 111: 'barrel',
 112: 'basket',
 113: 'waterfall',
 114: 'tent',
 115: 'bag',
 116: 'minibike',
 117: 'cradle',
 118: 'oven',
 119: 'ball',
 120: 'food',
 121: 'step',
 122: 'tank',
 123: 'trade name',
 124: 'microwave',
 125: 'pot',
 126: 'animal',
 127: 'bicycle',
 128: 'lake',
 129: 'dishwasher',
 130: 'screen',
 131: 'blanket',
 132: 'sculpture',
 133: 'hood',
 134: 'sconce',
 135: 'vase',
 136: 'traffic light',
 137: 'tray',
 138: 'ashcan',
 139: 'fan',
 140: 'pier',
 141: 'crt screen',
 142: 'plate',
 143: 'monitor',
 144: 'bulletin board',
 145: 'shower',
 146: 'radiator',
 147: 'glass',
 148: 'clock',
 149: 'flag'
 }

id2color = {
 0: [120, 120, 120],
 1: [180, 120, 120],
 2: [6, 230, 230],
 3: [80, 50, 50],
 4: [4, 200, 3],
 5: [120, 120, 80],
 6: [140, 140, 140],
 7: [204, 5, 255],
 8: [230, 230, 230],
 9: [4, 250, 7],
 10: [224, 5, 255],
 11: [235, 255, 7],
 12: [150, 5, 61],
 13: [120, 120, 70],
 14: [8, 255, 51],
 15: [255, 6, 82],
 16: [143, 255, 140],
 17: [204, 255, 4],
 18: [255, 51, 7],
 19: [204, 70, 3],
 20: [0, 102, 200],
 21: [61, 230, 250],
 22: [255, 6, 51],
 23: [11, 102, 255],
 24: [255, 7, 71],
 25: [255, 9, 224],
 26: [9, 7, 230],
 27: [220, 220, 220],
 28: [255, 9, 92],
 29: [112, 9, 255],
 30: [8, 255, 214],
 31: [7, 255, 224],
 32: [255, 184, 6],
 33: [10, 255, 71],
 34: [255, 41, 10],
 35: [7, 255, 255],
 36: [224, 255, 8],
 37: [102, 8, 255],
 38: [255, 61, 6],
 39: [255, 194, 7],
 40: [255, 122, 8],
 41: [0, 255, 20],
 42: [255, 8, 41],
 43: [255, 5, 153],
 44: [6, 51, 255],
 45: [235, 12, 255],
 46: [160, 150, 20],
 47: [0, 163, 255],
 48: [140, 140, 140],
 49: [250, 10, 15],
 50: [20, 255, 0],
 51: [31, 255, 0],
 52: [255, 31, 0],
 53: [255, 224, 0],
 54: [153, 255, 0],
 55: [0, 0, 255],
 56: [255, 71, 0],
 57: [0, 235, 255],
 58: [0, 173, 255],
 59: [31, 0, 255],
 60: [11, 200, 200],
 61: [255, 82, 0],
 62: [0, 255, 245],
 63: [0, 61, 255],
 64: [0, 255, 112],
 65: [0, 255, 133],
 66: [255, 0, 0],
 67: [255, 163, 0],
 68: [255, 102, 0],
 69: [194, 255, 0],
 70: [0, 143, 255],
 71: [51, 255, 0],
 72: [0, 82, 255],
 73: [0, 255, 41],
 74: [0, 255, 173],
 75: [10, 0, 255],
 76: [173, 255, 0],
 77: [0, 255, 153],
 78: [255, 92, 0],
 79: [255, 0, 255],
 80: [255, 0, 245],
 81: [255, 0, 102],
 82: [255, 173, 0],
 83: [255, 0, 20],
 84: [255, 184, 184],
 85: [0, 31, 255],
 86: [0, 255, 61],
 87: [0, 71, 255],
 88: [255, 0, 204],
 89: [0, 255, 194],
 90: [0, 255, 82],
 91: [0, 10, 255],
 92: [0, 112, 255],
 93: [51, 0, 255],
 94: [0, 194, 255],
 95: [0, 122, 255],
 96: [0, 255, 163],
 97: [255, 153, 0],
 98: [0, 255, 10],
 99: [255, 112, 0],
 100: [143, 255, 0],
 101: [82, 0, 255],
 102: [163, 255, 0],
 103: [255, 235, 0],
 104: [8, 184, 170],
 105: [133, 0, 255],
 106: [0, 255, 92],
 107: [184, 0, 255],
 108: [255, 0, 31],
 109: [0, 184, 255],
 110: [0, 214, 255],
 111: [255, 0, 112],
 112: [92, 255, 0],
 113: [0, 224, 255],
 114: [112, 224, 255],
 115: [70, 184, 160],
 116: [163, 0, 255],
 117: [153, 0, 255],
 118: [71, 255, 0],
 119: [255, 0, 163],
 120: [255, 204, 0],
 121: [255, 0, 143],
 122: [0, 255, 235],
 123: [133, 255, 0],
 124: [255, 0, 235],
 125: [245, 0, 255],
 126: [255, 0, 122],
 127: [255, 245, 0],
 128: [10, 190, 212],
 129: [214, 255, 0],
 130: [0, 204, 255],
 131: [20, 0, 255],
 132: [255, 255, 0],
 133: [0, 153, 255],
 134: [0, 41, 255],
 135: [0, 255, 204],
 136: [41, 0, 255],
 137: [41, 255, 0],
 138: [173, 0, 255],
 139: [0, 245, 255],
 140: [71, 0, 255],
 141: [122, 0, 255],
 142: [0, 255, 184],
 143: [0, 92, 255],
 144: [184, 255, 0],
 145: [0, 133, 255],
 146: [255, 214, 0],
 147: [25, 194, 194],
 148: [102, 255, 0],
 149: [92, 0, 255]
}