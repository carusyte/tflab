from __future__ import print_function
from tensorflow.examples.tutorials.mnist import input_data
from time import gmtime, strftime
import tensorflow as tf

print('%s begin data retrieval...' % strftime("%H:%M:%S"))
mnist = input_data.read_data_sets(
    '/tmp/tensorflow/mnist/input_data', source_url="http://yann.lecun.com/exdb/mnist/", one_hot=True)

print('%s begin model construction' % strftime("%H:%M:%S"))

x = tf.placeholder(tf.float32, [None, 784])
y_ = tf.placeholder(tf.float32, [None, 10])

def weight_variable(shape):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial)

def bias_variable(shape):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial)

def conv2d(x, W):
    return tf.nn.conv2d(x, W, [1,1,1,1], "SAME")

def max_pool_2x2(x):
    return tf.nn.max_pool(x,[1,2,2,1],[1,2,2,1],"SAME")

W_conv1 = weight_variable([5,5,1,32])
b_conv1 = bias_variable([32])

x_image = tf.reshape(x, [-1, 28, 28, 1])

h_conv1 = tf.nn.relu(conv2d(x_image, W_conv1) + b_conv1)
h_pool1 = max_pool_2x2(h_conv1)

W_conv2 = weight_variable([5, 5, 32, 64])
b_conv2 = bias_variable([64])

h_conv2 = tf.nn.relu(conv2d(h_pool1, W_conv2) + b_conv2)
h_pool2 = max_pool_2x2(h_conv2)

W_fc1 = weight_variable([7*7*64,1024])
b_fc1 = bias_variable([1024])

h_pool2_flat = tf.reshape(h_pool2, [-1, 7*7*64])
h_fc1 = tf.nn.relu(tf.matmul(h_pool2_flat, W_fc1)+b_fc1)

keep_prob = tf.placeholder(tf.float32)
h_fc1_drop = tf.nn.dropout(h_fc1, keep_prob)

W_fc2 = weight_variable([1024, 10])
b_fc2 = bias_variable([10])

y_conv = tf.matmul(h_fc1_drop,W_fc2) + b_fc2

cross_entropy = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y_, logits=y_conv))
train_step = tf.train.AdamOptimizer(1e-4).minimize(cross_entropy)
correct_prediction = tf.equal(tf.argmax(y_, 1), tf.argmax(y_conv, 1))
accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

print('%s training begins...' % strftime("%H:%M:%S"))

with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())
    print('%s variables initialized' % strftime("%H:%M:%S"))
    for i in range(20000):
        batch = mnist.train.next_batch(50)
        if i % 100 == 0:
            train_accuracy = sess.run(accuracy, feed_dict={x:batch[0], y_:batch[1], keep_prob:1.0})
            print('%s step %d accuracy %g' % (strftime("%H:%M:%S"), i, train_accuracy))
        sess.run(train_step, feed_dict={x:batch[0], y_:batch[1], keep_prob:0.66})
    print('%s test accuracy %g' % (strftime("%H:%M:%S"), sess.run(accuracy,
        feed_dict={x:mnist.test.images, y_:mnist.test.labels, keep_prob:1.0})))
