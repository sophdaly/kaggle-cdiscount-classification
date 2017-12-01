import tensorflow as tf
import pyprind
import numpy as np
import argparse
import yaml
from src.common import consts, paths
from src.training.train import train_dev_split
import os


# utility functions for weight and bias init
def weight_variable(shape):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial)


def bias_variable(shape):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial)


# tensorboard + layer utilities
def variable_summaries(var, name):
    """Attach a lot of summaries to a Tensor."""
    with tf.name_scope('summaries'):
        mean = tf.reduce_mean(var)
        tf.summary.scalar('mean/' + name, mean)
    with tf.name_scope('stddev'):
        stddev = tf.sqrt(tf.reduce_mean(tf.square(var - mean)))
        tf.summary.scalar('stddev/' + name, stddev)
        tf.summary.scalar('max/' + name, tf.reduce_max(var))
        tf.summary.scalar('min/' + name, tf.reduce_min(var))
        tf.summary.histogram(name, var)


def fc_layer(input_tensor, input_dim, output_dim, layer_name, act=tf.nn.relu):
    """Reusable code for making a simple neural net layer.

    It does a matrix multiply, bias add, and then uses relu to nonlinearize.
    It also sets up name scoping so that the resultant graph is easy to read,
    and adds a number of summary ops.
    """

    # Adding a name scope ensures logical grouping of the layers in the graph.
    with tf.name_scope(layer_name):
        # reshape input_tensor if needed
        input_shape = input_tensor.get_shape()
        if len(input_shape) == 4:
            ndims = np.int(np.product(input_shape[1:]))
            input_tensor = tf.reshape(input_tensor, [-1, ndims])
        # This Variable will hold the state of the weights for the layer
        with tf.name_scope('weights'):
            weights = weight_variable([input_dim, output_dim])
            variable_summaries(weights, layer_name + '/weights')
        with tf.name_scope('biases'):
            biases = bias_variable([output_dim])
            variable_summaries(biases, layer_name + '/biases')
        with tf.name_scope('Wx_plus_b'):
            preactivate = tf.matmul(input_tensor, weights) + biases
            tf.summary.histogram(layer_name + '/pre_activations', preactivate)
        activations = act(preactivate, 'activation')
        tf.summary.histogram(layer_name + '/activations', activations)

    return activations


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Default argument')
    parser.add_argument('-c', dest="config_filename", type=str, required=False, help='the config file name')
    args = parser.parse_args()

    if args.config_filename:
        with open(args.config_filename, 'r') as yml_file:
            cfg = yaml.load(yml_file)

        BATCH_SIZE = cfg["TRAIN"]["BATCH_SIZE"]
        EPOCHS_COUNT = cfg["TRAIN"]["EPOCHS_COUNT"]
        LEARNING_RATE = cfg["TRAIN"]["LEARNING_RATE"]
        TRAIN_TF_RECORDS = cfg["TRAIN"]["TRAIN_TF_RECORDS"]

        MODEL_NAME = cfg["MODEL"]["MODEL_NAME"]
        MODEL_LAYERS = cfg["MODEL"]["MODEL_LAYERS"]
    else:
        BATCH_SIZE = 64
        EPOCHS_COUNT = 5000
        LEARNING_RATE = 0.0001
        TRAIN_TF_RECORDS = paths.TRAIN_TF_RECORDS

        MODEL_NAME = consts.CURRENT_MODEL_NAME
        MODEL_LAYERS = consts.HEAD_MODEL_LAYERS

    with tf.Graph().as_default() as g, tf.Session().as_default() as sess:
        next_train_batch, get_dev_ds, get_train_sample_ds = \
            train_dev_split(sess, TRAIN_TF_RECORDS,
                            dev_set_size=consts.DEV_SET_SIZE,
                            batch_size=BATCH_SIZE,
                            train_sample_size=consts.TRAIN_SAMPLE_SIZE)

        dev_set = sess.run(get_dev_ds)
        dev_set_inception_feature = dev_set[consts.INCEPTION_OUTPUT_FIELD]
        dev_set_y_one_hot = dev_set[consts.LABEL_ONE_HOT_FIELD]

        train_sample = sess.run(get_train_sample_ds)
        train_sample_inception_feature = train_sample[consts.INCEPTION_OUTPUT_FIELD]
        train_sample_y_one_hot = train_sample[consts.LABEL_ONE_HOT_FIELD]

        # define model
        x = tf.placeholder(dtype=tf.float32, shape=(None, MODEL_LAYERS[0]), name="x")
        y = tf.placeholder(dtype=tf.int32, shape=(None), name="y")

        y_ = fc_layer(x, input_dim=2048, output_dim=5270, layer_name='FC_1', act=tf.identity)

        ###
        # loss and eval functions
        ###

        with tf.name_scope('cross_entropy'):
            cross_entropy_i = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y, logits=y_)
            cross_entropy = tf.reduce_mean(cross_entropy_i)
            tf.summary.scalar('cross_entropy', cross_entropy)

        with tf.name_scope('accuracy'):
            with tf.name_scope('correct_prediction'):
                # correct_prediction = tf.equal(tf.argmax(y,1), tf.argmax(y_,1))
                correct_prediction = tf.equal(tf.argmax(y_, 1, output_type=tf.int32), y)
            with tf.name_scope('accuracy'):
                accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
            tf.summary.scalar('accuracy', accuracy)

        # training step (NOTE: improved optimiser and lower learning rate; needed for more complex model)
        with tf.name_scope('train'):
            optimizer = tf.train.AdamOptimizer(LEARNING_RATE).minimize(cross_entropy)

        # Merge all the summaries and write them out to /summaries/conv (by default)
        merged = tf.summary.merge_all()

        train_writer = tf.summary.FileWriter(os.path.join(paths.SUMMARY_DIR, MODEL_NAME, '/train'))
        test_writer = tf.summary.FileWriter(os.path.join(paths.SUMMARY_DIR, MODEL_NAME, '/test'))

        # sess.run(tf.global_variables_initializer()
        tf.global_variables_initializer().run()

        saver = tf.train.Saver()

        bar = pyprind.ProgBar(EPOCHS_COUNT, update_interval=1, width=60)
        # main training loop
        for epoch in range(EPOCHS_COUNT):
            batch_examples = sess.run(next_train_batch)
            batch_inception_features = batch_examples[consts.INCEPTION_OUTPUT_FIELD]
            batch_y = batch_examples[consts.LABEL_ONE_HOT_FIELD]

            _, summary = sess.run([optimizer, merged], feed_dict={
                                      x: batch_inception_features,
                                      y: batch_y
                                  })

            train_writer.add_summary(summary, epoch)

            # Record summaries and test-set accuracy
            if epoch % 100 == 0 or epoch == EPOCHS_COUNT:

                dev_summaries = sess.run(merged, feed_dict={
                                          x: dev_set_inception_feature,
                                          y: dev_set_y_one_hot
                                      })
                test_writer.add_summary(dev_summaries, epoch)

                saver.save(sess, os.path.join(paths.CHECKPOINTS_DIR, MODEL_NAME),
                           latest_filename=MODEL_NAME + '_latest')
            bar.update()
