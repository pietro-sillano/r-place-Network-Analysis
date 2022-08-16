# trimmed version

# wget --load-cookies /tmp/cookies.txt "https://docs.google.com/uc?export=download&confirm=$(wget --quiet --save-cookies /tmp/cookies.txt --keep-session-cookies --no-check-certificate 'https://docs.google.com/uc?export=download&id=1nu_EprKEI7h1g9Y-q9xO3S5eIoG91dET' -O- | sed -rn 's/.*confirm=([0-9A-Za-z_]+).*/\1\n/p')&id=1nu_EprKEI7h1g9Y-q9xO3S5eIoG91dET" -O reddit_trimmed.csv && rm -rf /tmp/cookies.txt





# gzipped full version
mkdir data
wget -c -r -np -p -4 https://placedata.reddit.com/data/canvas-history/2022_place_canvas_history.csv.gzip ./
tar -xzvf ./placedata.reddit.com/data/canvas-history/2022_place_canvas_history.csv.gzip -C ./data
rm ./placedata.reddit.com/data/canvas-history/2022_place_canvas_history.csv.gzip


https://github.com/pietro-sillano/SindyPendulum/blob/main/README.md
