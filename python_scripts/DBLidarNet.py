from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf
import network_layers

class DBLidarNet:
  def __init__(self, FLAGS):
    self._learning_rate = tf.convert_to_tensor(FLAGS.learning_rate)
    self._growth = FLAGS.growth
    self._num_classes = FLAGS.num_classes
    self._eta = FLAGS.eta
    self.input_data = tf.placeholder(tf.float32, shape=[None,
                                                        FLAGS.image_height,
                                                        FLAGS.image_width,
                                                        FLAGS.num_channels],
                                     name="input_data")
    self.labels = tf.placeholder(tf.float32, shape=[None,
                                                    FLAGS.image_height,
                                                    FLAGS.image_width,
                                                    FLAGS.num_classes],
                                 name="labels")
    self.keep_prob = tf.placeholder(tf.float32, name="keep_prob")
    self.is_training = tf.placeholder(tf.bool, name="is_training")
    self._weights = np.loadtxt('weights_squeeze_seg.txt')
    self._train_summary_list = []
    self._val_summary_list = []
    self._viz_summary_list = []
  def _loss_function(self):
    """ loss function """
    logits = tf.reshape(self.prediction, (-1, self._num_classes))
    epsilon = tf.constant(value=1e-4)
    labels = tf.cast(tf.reshape(self.labels, (-1, self._num_classes)), 
                     tf.float32)
    softmax = tf.nn.softmax(logits) + epsilon
    cross_entropy = -tf.reduce_sum(tf.multiply(labels * tf.log(softmax),
                                               self._weights),
                                   reduction_indices=[1])
    self.cross_entropy_mean = tf.reduce_mean(cross_entropy,
                                             name='xentropy_mean')
    tf.add_to_collection('cross_entropy_loss', self.cross_entropy_mean)
    vars_ = tf.trainable_variables()
    reg_loss_val = tf.add_n([tf.nn.l2_loss(v) for v in vars_ if
                             len(v.get_shape().as_list()) > 1])
    tf.add_to_collection('reg_loss', self._eta * reg_loss_val)
    self._loss_value = tf.add_n(tf.get_collection('cross_entropy_loss')
                                + tf.get_collection('reg_loss'),
                                name='cls_loss')
    self._train_summary_list.append(tf.summary.scalar('train loss',
                                                      self.cross_entropy_mean))
    self._val_summary_list.append(tf.summary.scalar('validation loss',
                                                    self.cross_entropy_mean))
  def _encoder(self):
    """ encoder definition
    """
    conv_0 = network_layers.conv_2d(self.input_data, 48, 3, 1, 'SAME', 'conv_0')
    conv_1 = network_layers.conv_2d(conv_0, 48, 3, 1, 'SAME', 'conv_1')

    self._dense_block_0, features, _ = network_layers.add_block(
        "dense_block_0", conv_1, 6, 48, 3, self._growth, self.is_training)

    transition_0 = tf.nn.max_pool(self._dense_block_0, [1, 2, 2, 1],
                                  [1, 2, 2, 1], 'VALID')
    self._dense_block_1, features, _ = network_layers.add_block(
        "dense_block_1", transition_0, 8, features, 3, self._growth,
        self.is_training)

    transition_1 = tf.nn.max_pool(self._dense_block_1, [1, 2, 2, 1],
                                  [1, 2, 2, 1], 'VALID')

    dense_block_2, features, _ = network_layers.add_block(
        "dense_block_2", transition_1, 10, features, 3, self._growth,
        self.is_training)

    _, features, self._db_output_3 = network_layers.add_block(
        "dense_block_3", dense_block_2, 15, features, 3, self._growth,
        self.is_training)
    print('encoder')
  def _decoder(self):
    """ decoder definition
    """
    shape = self._db_output_3.get_shape().as_list()
    upconv_0 = network_layers.transpose_conv_2d(self._db_output_3, shape[3],
                                                3, 2, 'SAME', "upconv_0")
    shape = self._dense_block_1.get_shape().as_list()
    crop = tf.image.resize_image_with_crop_or_pad(upconv_0, shape[1], shape[2])
    skip_0 = tf.concat([crop, self._dense_block_1], axis=3)
    shape = tf.shape(skip_0)
    _, features, db_output_4 = network_layers.add_block(
        "dense_block_4", skip_0, 8, shape[3], 3, self._growth,
        self.is_training, depth_separable=True)
    shape = db_output_4.get_shape().as_list()
    upconv_1 = network_layers.transpose_conv_2d(db_output_4, shape[3], 3, 2,
                                                'SAME', "upconv_1")
    shape = self._dense_block_0.get_shape().as_list()
    crop = tf.image.resize_image_with_crop_or_pad(upconv_1, shape[1], shape[2])
    skip_1 = tf.concat([crop, self._dense_block_0], axis=3)
    shape = tf.shape(skip_1)
    _, features, db_output_5 = network_layers.add_block(
        "dense_block_5", skip_1, 6, shape[3], 3, self._growth, self.is_training,
        depth_separable=True)

    self.prediction = network_layers.conv_2d(db_output_5, self._num_classes, 1,
                                             1, 'SAME', "prediction")
  def _optimize_function(self):
    """ optimization function """
    update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
    with tf.control_dependencies(update_ops):
      return tf.train.AdamOptimizer(self._learning_rate).minimize(self._loss_value)
  def _calculate_iou(self):
    """ Calculating validation IoU and storing summaryfor visualizing
        predicted segmentation mask
    """
    gt_mask = tf.argmax(self.labels, 3)
    predicted_mask = tf.argmax(self.prediction, 3)
    segmentation_viz = tf.cast(tf.greater(gt_mask, 0), tf.float32)
    segmentation_viz = tf.expand_dims(segmentation_viz, axis=3)
    predicted_mask_viz = tf.cast(tf.greater(predicted_mask, 0), tf.float32)
    predicted_mask_viz = tf.expand_dims(predicted_mask_viz, axis=3)
    segmentation_viz = tf.concat((segmentation_viz, predicted_mask_viz), axis=1)
    self.viz_summary_list.append(
        tf.summary.image("Above: ground truth mask,below: predicted mask",
                         segmentation_viz))
    gt_mask = tf.greater(gt_mask, 0)
    predicted_mask = tf.greater(predicted_mask, 0)
    intersection = tf.reduce_sum(tf.cast(tf.logical_and(gt_mask,
                                                        predicted_mask),
                                         tf.float32))
    union = tf.reduce_sum(tf.cast(predicted_mask, tf.float32)) + \
        tf.reduce_sum(tf.cast(gt_mask, tf.float32)) - intersection
    self._IoU = tf.cond(tf.equal(union, 0), lambda: 0.0, lambda: intersection/union)
    self._val_summary_list.append(tf.summary.scalar('validation IoU',
                                                    self._IoU))
  @property
  def loss_value(self):
    return self._loss_value
  @property
  def IoU(self):
    return self._IoU
  @property
  def train_summary_list(self):
    return self._train_summary_list
  @property
  def val_summary_list(self):
    return self._val_summary_list
  @property
  def viz_summary_list(self):
    return self._viz_summary_list
  def _add_summaries(self):
    """initializing summary
    """
    self._calculate_iou()
    merged = tf.summary.merge_all()
  def build_graph(self):
    """ bulding graph
    """
    self._encoder()
    self._decoder()
    self._loss_function()
    self.train_step = self._optimize_function()
    self._add_summaries()
