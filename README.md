# place_network


- trimming.ipynb : reduce size of the reddit dataset, changes datatypes, simplify user_id, separate coordinates, converts timestamp to integers in ms. From 20 Gb to 4 Gb. Its output is reddit_place_2022_trimmed.csv


- network_analysis.ipynb : some copypasta codes for network analysis. no useful output

- read_json.ipynb: from json atlas from Atlas2 website convert to artwork list ordered by area. Output os artwork_ordered.csv

- bipartite_network.ipynb create bipartite network from reddit_place_2022_trimmed.csv and artwork_ordered.csv 

- process_network_colab.ipynb da runnare su COLAB per generare la rete degli utenti