DATA_FOLDER="./data"
ZIP_FILE="README.tar.gz"
echo $FILE


# mkdir $DATA_FOLDER
# wget -c  -4 https://raw.githubusercontent.com/pietro-sillano/SindyPendulum/main/README.md -O ./data/README.md


tar -xzvf $DATA_FOLDER/$ZIP_FILE -C $DATA_FOLDER
# rm ./placedata.reddit.com/data/canvas-history/2022_place_canvas_history.csv.gzip


