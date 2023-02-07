# Network of collaborations in r/Place 2022
I thought that it would have been cool to study and try to visualize the interaction between contributors of the Reddit Place 2022 event. If you don't know what it is: [r/place](https://www.reddit.com/r/place/) or watch the [timelapse](https://www.youtube.com/watch?v=K5O3UgLG2Jw).

I took a network science course titled **[Complexity in social systems](https://fisica-sc.campusnet.unito.it/do/corsi.pl/Show?_id=4ef1)** and decided to bring this work as final project and it was really appreciated (or maybe I just have been lucky to have the professor nerdy enough to appreciate it).

![plot](assets/img/pic.png)


## Description
The initial question of the project was if it's possible to group contributors in communities based on which artwork they have contributed to.
It turns out to be not an easy task due to the **huge** number of users and their activity. To give an idea:
- 160 million pixel modified
- 10 million unique users
- almost 10k different artworks

Then I had to make some simplifying assumptions. Unfortunately, it would be difficult to explain here every step, but [here](https://github.com/pietro-sillano/r-place-Network-Analysis/blob/main/docs/Reddit_place_ENG.pdf) you can find the presentation slides with the main steps.

# Results
<img src = "assets/plot/projections/arts_weighted.png" width ="170" /> <img src = "assets/plot/projections_communities/arts_weighted.png" width ="170" /> <img src = "assets/plot/projections/arts_weighted_100_2nd.png" width ="170" /> <img src = "assets/plot/projections_communities/arts_weighted_100_2nd.png" width ="170" />

That's the **network representation** for 25 (and 100) artworks respectively. Each node is an artwork and nodes linked together share contributing users. The width of the link represents the number of shared users.

The figures with coloured nodes are the network representation after the community detection algorithm (Newman modularity algorithm). Communities are different artworks that shared same users. This could be a signal for **collaboration** and **competition** too.

# Future developments
- Analyze the collaboration / competition relationships

- Consider the dynamics and evolution of the canvas over time

# In Details
```
├── notebooks
     |
     ├─ 00_statistics_figures.ipynb Some statistics and plots of the dataset
     |
     ├─ 01_bipartite_network.ipynb create bipartite network of contributing users and artworks
     |
     ├─ 02_A_Analysis.ipynb Analysis for the 25 artworks selection
     |
     ├─ 02_B_Analysis.ipynb Analysis for the 100 artworks selection

├── scripts
     │
     └────  trimming.py: reduce size of the Reddit dataset, changes datatypes,
    simplify user_id, separates coordinates, converts timestamp to integers in ms. From 20 Gb to 4 Gb.
```



# Contributing
Any kind of suggestion or contribution is welcomed.
