from bson import BSON
import random, bson
from tqdm import tqdm
import argparse
import os


def split_bson(input_bson_filename, output_bson_filename_1, output_bson_filename_2, n, number_random_example):

    data = bson.decode_file_iter(open(input_bson_filename, 'rb'))

    random_items = random.sample(range(n), number_random_example)
    random_items.sort()
    print(random_items[0])
    r_idx = 0
    print(n)
    with open(output_bson_filename_1, 'w+') as output:
        for c, d in tqdm(enumerate(data), total=n):
            if c != random_items[r_idx]:
                continue
            else:
                # print("pick random item: {}".format(c))
                # insert your code here.
                output.write(BSON.encode(d))
                r_idx = r_idx + 1
                if r_idx == number_random_example:
                   break
    r_idx = 0
    data = bson.decode_file_iter(open(input_bson_filename, 'rb'))
    with open(output_bson_filename_2, 'w+') as output:
        for c, d in tqdm(enumerate(data), total=n):
            if r_idx<number_random_example and c == random_items[r_idx]:
                r_idx = r_idx +1
                continue
            else:

                output.write(BSON.encode(d))
    print("Finish convert tfrecords with {} records".format(r_idx))


def random_sample_bson(input_bson_filename, output_bson_filename,  n=100, number_random_example=10):

    data = bson.decode_file_iter(open(input_bson_filename, 'rb'))

    random_items = random.sample(range(n), number_random_example)
    random_items.sort()

    r_idx = 0

    with open(output_bson_filename, 'w+') as output:
        for c, d in tqdm(enumerate(data), total=n):
            if c != random_items[r_idx]:
                continue
            else:
                # print("pick random item: {}".format(c))
                # insert your code here.
                output.write(BSON.encode(d))
                r_idx = r_idx + 1
                if r_idx >= number_random_example:
                    break

    print("Finish convert tfrecords with {} records".format(r_idx))


def split_sample_bson(input_bson_filename, output_bson_dir, n=100, split=10):

    data = bson.decode_file_iter(open(input_bson_filename, 'rb'))

    no_example_per_split = int(n / split)
    print("total number of sample per split: {}".format(no_example_per_split))

    for c, d in tqdm(enumerate(data), total=n):

        f_n = int(c % split)

        output = open(os.path.join(output_bson_dir, "{}_{}.bson".format(f_n, no_example_per_split)), 'a+')

        output.write(BSON.encode(d))

    print("Finish convert tfrecords with {} records".format(c+1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-i', dest="full_bson_filename", type=str, required=True, help='the input file in bson format')
    parser.add_argument('-o', dest="subset_bson_filename", type=str, required=True, help='the output file in bson format')
    parser.add_argument('-n', dest="total_records", type=int, required=True, help='number of records to convert.')
    parser.add_argument('-r', dest="number_of_random_records", type=int, required=True, help='number of random records to convert.')
    args = parser.parse_args()

    # random_sample_bson(args.full_bson_filename, args.subset_bson_filename,
    #                    n=args.total_records, number_random_example=args.number_of_random_records)
    split_bson(args.full_bson_filename, args.subset_bson_filename,
                      n=args.total_records, split=args.number_of_random_records)
