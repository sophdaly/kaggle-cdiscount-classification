import tensorflow as tf
import sys
from src.common import consts
import freeze
from src.common import paths
from sklearn import preprocessing
import os
import re
import numpy as np
from skimage.data import imread
import io
from src.common.paths import INCEPTION_MODEL_DIR


class NodeLookup(object):
    def __init__(self,
                 model_dir=INCEPTION_MODEL_DIR,
                 label_lookup_path=None,
                 uid_lookup_path=None):
        if not label_lookup_path:
            label_lookup_path = os.path.join(model_dir, 'imagenet_2012_challenge_label_map_proto.pbtxt')
        if not uid_lookup_path:
            uid_lookup_path = os.path.join(model_dir, 'imagenet_synset_to_human_label_map.txt')
        self.node_lookup = self.load(label_lookup_path, uid_lookup_path)

    def load(self, label_lookup_path, uid_lookup_path):
        if not tf.gfile.Exists(uid_lookup_path):
            tf.logging.fatal('File does not exist %s', uid_lookup_path)
        if not tf.gfile.Exists(label_lookup_path):
            tf.logging.fatal('File does not exist %s', label_lookup_path)

        # Loads mapping from string UID to human-readable string
        proto_as_ascii_lines = tf.gfile.GFile(uid_lookup_path).readlines()
        uid_to_human = {}
        p = re.compile(r'[n\d]*[ \S,]*')
        for line1 in proto_as_ascii_lines:
            parsed_items = p.findall(line1)
            uid = parsed_items[0]
            human_string = parsed_items[2]
            uid_to_human[uid] = human_string

        # Loads mapping from string UID to integer node ID.
        node_id_to_uid = {}
        proto_as_ascii = tf.gfile.GFile(label_lookup_path).readlines()
        for line1 in proto_as_ascii:
            if line1.startswith('  target_class:'):
                target_class = int(line1.split(': ')[1])
            if line1.startswith('  target_class_string:'):
                target_class_string = line1.split(': ')[1]
                node_id_to_uid[target_class] = target_class_string[1:-2]

        # Loads the final mapping of integer node ID to human-readable string
        node_id_to_name = {}
        for key, val in node_id_to_uid.items():
            if val not in uid_to_human:
                tf.logging.fatal('Failed to locate: %s', val)
            name = uid_to_human[val]
            node_id_to_name[key] = name

        return node_id_to_name

    def id_to_string(self, node_id):
        if node_id not in self.node_lookup:
            return ''
        return self.node_lookup[node_id]


def inception_model():
    tensors = freeze.unfreeze_into_current_graph(paths.IMAGENET_GRAPH_DEF,
                                                 tensor_names=[
                                                     consts.INCEPTION_INPUT_STRING_TENSOR,
                                                     consts.INCEPTION_OUTPUT_TENSOR])

    def forward(_sess, _image_raw):
        _out = _sess.run(tensors[consts.INCEPTION_OUTPUT_TENSOR],
                         {tensors[consts.INCEPTION_INPUT_STRING_TENSOR]: _image_raw})
        return _out

    return forward


def inception_image_model():
    tensors = freeze.unfreeze_into_current_graph(paths.IMAGENET_GRAPH_DEF,
                                                 tensor_names=[
                                                     consts.INCEPTION_INPUT_ARRAY_TENSOR,
                                                     consts.INCEPTION_OUTPUT_TENSOR])

    def forward(_sess, _image_array):
        _out = _sess.run(tensors[consts.INCEPTION_OUTPUT_TENSOR],
                         {tensors[consts.INCEPTION_INPUT_ARRAY_TENSOR]: _image_array})
        return _out

    return forward


def inception_inference():
    tensors = freeze.unfreeze_into_current_graph(paths.IMAGENET_GRAPH_DEF,
                                                 tensor_names=[
                                                     consts.INCEPTION_INPUT_STRING_TENSOR,
                                                     "softmax:0"])

    def forward(sess, image_raw):
        label_vect = sess.run(tensors["softmax:0"], {tensors[consts.INCEPTION_INPUT_STRING_TENSOR]: image_raw})
        return label_vect

    return forward


def inception_batch_inference():
    tensors = freeze.unfreeze_into_current_graph(paths.IMAGENET_GRAPH_DEF,
                                                 tensor_names=[
                                                     consts.INCEPTION_INPUT_ARRAY_TENSOR,
                                                     "softmax:0"])

    def forward(sess, _img):
        label_vect = sess.run(tensors["softmax:0"], {tensors[consts.INCEPTION_INPUT_ARRAY_TENSOR]: _img})
        return label_vect

    return forward


'''
The inception is only able to inference one image at a time.
'''
if __name__ == '__main__':

    with tf.Session().as_default() as sess:
        # image_raw_1 = tf.read_file('data/images/airedale.jpg').eval()
        # image_raw_1 = tf.read_file('data/inception-imgs/tiger_shark.jpg').eval()

        img_batch = np.zeros([2, 299, 299, 3], float)
        img1 = imread('data/inception-imgs/tiger_shark.jpg')
        img_batch[0, :] = img1
        img_batch[1, :] = img1
        print(img_batch.shape)

        g = tf.Graph()
        sess = tf.Session(graph=g)

        with g.as_default():
            model = inception_batch_inference()

        with g.as_default():
            out = model(sess, img_batch)
            predictions = np.squeeze(out)
            print(predictions.shape)

            node_lookup = NodeLookup()

            top_5 = predictions.argsort()[-5:][::-1]
            for node_id in top_5:
                human_string = node_lookup.id_to_string(node_id)
                score = predictions[node_id]
                print('%d %s (score = %.5f)' % (node_id, human_string, score))

