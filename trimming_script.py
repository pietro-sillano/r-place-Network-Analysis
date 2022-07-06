import pandas as pd
from tqdm import tqdm
from datetime import datetime


START_TIME = 1648806250315


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
    timestamp *= 1000.0
    timestamp = int(timestamp)

    # The earliest timestamp is 1648806250315, so subtract that from each timestamp
    # to get the time in milliseconds since the beginning of the experiment.
    timestamp -= START_TIME

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



def process_chunk_v2(chunk, df,counter,mapping):
    chunk["timestamp"] = chunk["timestamp"].astype("uint32")
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