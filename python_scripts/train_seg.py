from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import math

import tensorflow as tf
import cv2
import time
from os import listdir
from os.path import isfile, join

import network_layers
from DBLidarNet import *
import utils

def main():
 
  FLAGS = tf.app.flags.FLAGS
  tf.app.flags.DEFINE_string('model_name', 'lidar_segmentation', 
      """model name""")
  tf.app.flags.DEFINE_string('train_record_filename', '',
      """path to train record""")
  tf.app.flags.DEFINE_string('validation_record_filename', '',
      """path to test record""")
  
  tf.app.flags.DEFINE_string('log_dir', '',
      """path to log directory""")



  
  tf.app.flags.DEFINE_float('learning_rate', 0.0001, """learning rate""")
  tf.app.flags.DEFINE_float('eta', 0.0005, """l2 norm coefficient""")
  
  tf.app.flags.DEFINE_integer('total_epochs', 200, 
      """total epochs for training""")
  tf.app.flags.DEFINE_integer('batch_size', 4, """batch size""")
  tf.app.flags.DEFINE_integer('image_height', 64, """image height""")
  tf.app.flags.DEFINE_integer('image_width', 324, """image width""")
  tf.app.flags.DEFINE_integer('num_channels', 5, """number of channels""")
  tf.app.flags.DEFINE_integer('num_classes', 4, """number of classes""")
  tf.app.flags.DEFINE_integer('growth', 16, """dense block growth rate""")


  if FLAGS.train_record_filename == '':
    print ('train record filename not specified')
    return
  if FLAGS.validation_record_filename == '':
    print ('validation record filename not specified')
    return
  if FLAGS.model_name == 'lidar_segmentation':
    print ('model name set to %s' % FLAGS.model_name)
  if FLAGS.log_dir == '':
    FLAGS.log_dir = '../logs/' + FLAGS.model_name
    print ('log directory set to to %s' % FLAGS.log_dir)

  tfrecord_train_files = [f for f in listdir(FLAGS.train_record_filename) if isfile(join(FLAGS.train_record_filename , f))]

  
  tfrecord_validation_files = [f for f in listdir(FLAGS.validation_record_filename) if isfile(join(FLAGS.validation_record_filename , f))]


  for index in range(len(tfrecord_train_files)):
    tfrecord_train_files[index] = FLAGS.train_record_filename + tfrecord_train_files[index]
    
    
  for index in range(len(tfrecord_validation_files)):
    tfrecord_validation_files[index] = FLAGS.validation_record_filename + tfrecord_validation_files[index]

  
  
  model = DBLidarNet(FLAGS) 
  print('constructor done')
  model.build_graph()
#  raw_input()

  total_parameters = 0
  for variable in tf.trainable_variables():
    shape = variable.get_shape()
    variable_parameters = 1
    for dim in shape:
      variable_parameters *= dim.value
    total_parameters += variable_parameters
  print(total_parameters)
  train_data_size = 0 
  for tf_file in tfrecord_train_files:
    for record in tf.python_io.tf_record_iterator(tf_file):
      train_data_size+=1
  val_data_size = 0 
  for tf_file in tfrecord_validation_files:
    for record in tf.python_io.tf_record_iterator(tf_file):
      val_data_size+=1


  train_iterator = utils.prepare_dataset(tfrecord_train_files, FLAGS, train_data_size)
  image_train, annotation_train = train_iterator.get_next()  
      
  validation_iterator = utils.prepare_dataset(tfrecord_validation_files,FLAGS, val_data_size)
  image_validation, annotation_validation = validation_iterator.get_next()  

      
  steps_per_epoch = train_data_size//FLAGS.batch_size
  init_op = tf.group(tf.global_variables_initializer(),
                     tf.local_variables_initializer())

  train_loss = 0.0
  val_loss = 0.0
  val_IoU = 0.0
  train_writer = tf.summary.FileWriter(FLAGS.log_dir + '/train',sess.graph)
  test_writer = tf.summary.FileWriter(FLAGS.log_dir + '/test')
  sess.run(init_op)

  training_steps = 0
  epochs_completed = 0
  validation_size = 250

  save_steps = steps_per_epoch * 5

  ckpt_saver = tf.train.Saver(tf.global_variables(),max_to_keep=80)
  while True: 
    try:
      image, mask = sess.run([image_train, annotation_train])
      mask = np.int32(mask)
      feed_dict={model.input_data:image, model.labels:mask, model.keep_prob:1.0,
                 model.is_training:True}
      _,l, train_summary = sess.run([model.train_step, 
                                    model.loss_value, 
                                    model.train_summary_list],
                                    feed_dict=feed_dict)
      train_loss+=l
      if(training_steps % steps_per_epoch == 0 and training_steps > 0):
        if(epochs_completed % 5  == 0 and epochs_completed > 100):
          model_name = '../models/' + FLAGS.model_name + '_' +  str(epochs_completed) + '.ckpt'
          ckpt_saver.save(sess, model_name)
        print ('train loss: %f, epochs: %d' % ((train_loss/steps_per_epoch), 
                epochs_completed))
        train_loss = 0.0
        for iteration in range(0,validation_size):
          image, mask = sess.run([image_validation, annotation_validation])
          mask = np.int32(mask)
          feed_dict={model.input_data:image, model.labels:mask, 
                     model.keep_prob:1.0, model.is_training:False}
          l, IoU, val_summary, viz_summary = sess.run([model.loss_value, 
                                                     model.IoU,
                                                     model.val_summary_list,
                                                     model.viz_summary_list,
                                                    ],feed_dict=feed_dict)
          val_loss+=l
          val_IoU+=IoU
        print ('test loss: %f, val IoU: %f' % (val_loss/(validation_size), 
              val_IoU/(validation_size)))

        for sum_str in train_summary:
          train_writer.add_summary(sum_str, epochs_completed) 
        for sum_str in val_summary:
          test_writer.add_summary(sum_str, epochs_completed)  
        for sum_str in viz_summary:
          test_writer.add_summary(sum_str, epochs_completed)  

        epochs_completed+=1
        val_loss = 0.0
        val_IoU = 0.0
      training_steps+=1
    except tf.errors.OutOfRangeError:
      
      print('Done training -- epoch limit reached')
      print (training_steps)
      train_writer.close()
      test_writer.close()
      break

if __name__ == '__main__':
  main()
