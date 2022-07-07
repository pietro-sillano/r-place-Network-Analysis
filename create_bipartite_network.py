import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
from tqdm.auto import tqdm
from matplotlib.path import Path
import ast
import pickle
import matplotlib.pyplot as plt
#from networkx.algorithms import bipartite
#import networkx as nx


df = pd.read_csv("artworks_ordered.csv")
df = df[:5]


artworks = {}
id_count = 1
for row in df.itertuples():
    name = row.name
    path = row.path
    path = ast.literal_eval(path)
    coords = list(path.values())[0]
    artworks[id_count] = coords
    id_count += 1
    
    
    
def find_points(art):
    x, y = np.meshgrid(np.arange(2000), np.arange(2000)) # make a canvas with coordinates
    x, y = x.flatten(), y.flatten()
    points = np.vstack((x,y)).T 

    p = Path(art) # make a polygon
    grid = p.contains_points(points,radius = 0)
    mask = grid.reshape(2000,2000) # now you have a mask with points inside a polygon
    x,y = mask.nonzero()
    coords = []
    for xc,yc in zip(x,y):
        coords.append((xc,yc))
    return coords




CHUNK_SIZE = 3_000_000
MIN_TILES = 200

f = open('bipartite_network' + str(MIN_TILES) + '.csv', 'w')
counter = 0

for key in tqdm(artworks.keys()):
    art_pixel = find_points(artworks[key])
    s = set(art_pixel)
    name = key
    user_actions = {}
    l = []


    with pd.read_csv(
            'reddit_place_2022_trimmed.csv',
            chunksize=CHUNK_SIZE,
            engine="c",
            dtype={'timestamp':np.uint32,
              'user_id':np.uint32,
              'pixel_color':np.uint8,
              'x':np.uint16,
              'y':np.uint16,}
        ) as csv:
            for chunk in tqdm(csv):
                for row in chunk.itertuples():
                    user = row.user_id
                    x = row.x
                    y = row.y
                    if (x,y) in s:
                        if  user in user_actions:
                            user_actions[user] = user_actions[user] + 1 
                        else:
                            user_actions[user] = 1
               
    for user_key in user_actions.keys():
        if user_actions[user_key] > MIN_TILES:
            f.write(str(name) + ' ' + str(user_key) + '\n')
            l.append(user_actions[user_key])
            counter +=  1
            
    pickle.dump(l, open('./output/tiles/distrib_tiles_' + str(name) + '.pickle', "wb")) 
    print(counter)
f.close()