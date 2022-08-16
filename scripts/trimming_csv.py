import pandas as pd
from tqdm import tqdm
from datetime import datetime

# The length of time in milliseconds after 1970-01-01T00:00:00.000 UTC that
# the first pixel was placed in r/Place 2022.
START_TIME  = 1648806250 #begin of place in s

def parse_timestamp(timestamp):
    """Convert a YYYY-MM-DD HH:MM:SS.SSS timestamp to milliseconds after the start of r/Place 2022."""
    date_format = "%Y-%m-%d %H:%M:%S.%f"
    try:
        # Remove the UTC timezone from the timestamp and convert it to a POSIX timestamp.
        timestamp = datetime.strptime(timestamp[:-4], date_format).timestamp()
    except ValueError:
        # The timestamp is exactly on the second, so there is no decimal (%f).
        # This happens 1/1000 of the time.
        timestamp = datetime.strptime(timestamp[:-4], date_format[:-3]).timestamp()

    # Convert from a float in seconds to an int in milliseconds
    #timestamp *= 1000.0
    #timestamp = int(timestamp)

    # The earliest timestamp is 1648806250315, so subtract that from each timestamp
    # to get the time in milliseconds since the beginning of the experiment.
    timestamp = timestamp -  START_TIME
    timestamp = float(timestamp) / 60.
    timestamp = int(timestamp)
    return timestamp

def parse_pixel_color(pixel_color):
    """Convert a hex color code to an integer key."""
    hex_to_key = {
        "#000000": 0,
        "#00756F": 1,
        "#009EAA": 2,
        "#00A368": 3,
        "#00CC78": 4,
        "#00CCC0": 5,
        "#2450A4": 6,
        "#3690EA": 7,
        "#493AC1": 8,
        "#515252": 9,
        "#51E9F4": 10,
        "#6A5CFF": 11,
        "#6D001A": 12,
        "#6D482F": 13,
        "#7EED56": 14,
        "#811E9F": 15,
        "#898D90": 16,
        "#94B3FF": 17,
        "#9C6926": 18,
        "#B44AC0": 19,
        "#BE0039": 20,
        "#D4D7D9": 21,
        "#DE107F": 22,
        "#E4ABFF": 23,
        "#FF3881": 24,
        "#FF4500": 25,
        "#FF99AA": 26,
        "#FFA800": 27,
        "#FFB470": 28,
        "#FFD635": 29,
        "#FFF8B8": 30,
        "#FFFFFF": 31,
    }

    return hex_to_key[pixel_color]

def split_coords_single_points(points):
    """
    Given a dataframe containing only rows that have single-point
    coordinates, split the coordinates into x and y columns.
    """

    # Convert the coordinate column to a list of strings.
    points["coordinate"] = points["coordinate"].apply(lambda x: x.split(","))

    # Create new x and y columns from the coordinate column.
    points["x"] = points["coordinate"].apply(lambda x: x[0]).astype("uint16")
    points["y"] = points["coordinate"].apply(lambda x: x[1]).astype("uint16")

    # Drop the coordinate column.
    del points["coordinate"]

    return points

def process_chunk(chunk, df,counter,mapping):
    chunk["timestamp"] = chunk["timestamp"].astype("uint16")
    chunk["pixel_color"] = chunk["pixel_color"].astype("uint8")

    # per rimuovere le azioni degli admin
    chunk.drop(chunk[chunk["coordinate"].str.count(",") == 3].index,inplace=True)

    chunk = split_coords_single_points(chunk)

    for user in chunk.user_id:
        if not user in mapping:
            mapping[user] = counter
            counter += 1

    chunk["user_id"] = chunk["user_id"].map(mapping)
    chunk["user_id"] = chunk["user_id"].astype("uint32")

    df = pd.concat((df, chunk), ignore_index=True)

    return df,counter,mapping

CHUNK_SIZE = 1000000

def trim(infile_path, outfile_path):
    """Trim the infile data and write it to outfile."""
    df = pd.DataFrame(columns=["timestamp", "user_id","pixel_color", "x", "y"])
    df["timestamp"] = df["timestamp"].astype("uint32")
    df["pixel_color"] = df["pixel_color"].astype("uint8")
    df["user_id"] = df["user_id"].astype("uint32")

    df["x"] = df["x"].astype("uint16")
    df["y"] = df["y"].astype("uint16")

    mapping = {}
    counter = 0

    with pd.read_csv(
        infile_path,
        usecols=["timestamp", "user_id","pixel_color", "coordinate"],
        converters={
            "timestamp": parse_timestamp,
            "pixel_color": parse_pixel_color,
        },
        chunksize=CHUNK_SIZE,
        engine="c",
        #compression="gzip",
    ) as csv:
        for chunk in tqdm(csv):
            df, counter, mapping = process_chunk(chunk, df,counter,mapping)
            df.sort_values("timestamp", inplace=True, ignore_index=True)
    print(counter)
    df.to_csv(outfile_path, sep=',', index=False)
    return df

infile_path = "..data/2022_place_canvas_history.csv"
outfile_path = "..output/reddit_trimmed.csv"

df_trim = trim(infile_path, outfile_path)
