from __future__ import print_function
import __main__ as main
import pandas as pd
import mysql.connector
import numpy as np
import tensorflow as tf
from pstk import data as dat
from sqlalchemy import create_engine
from joblib import Parallel, delayed
from pstk.model.wavenet import time_to_batch


def testGetFileName():
    print(main.__file__)


def testEmbedding():
    sess = tf.InteractiveSession()
    word_embeddings = tf.get_variable(
        "word_embeddings", [5, 5], initializer=tf.truncated_normal_initializer())
    sess.run(tf.global_variables_initializer())
    word_ids = [0, 0, 1, 2]
    embedded_word_ids = tf.nn.embedding_lookup(word_embeddings, word_ids)
    r = embedded_word_ids.eval()
    print("{}".format(r))
    print(r.shape)


def getIndices(x, n):
    print("x:{}".format(x.get_shape()))
    indices = tf.stack([tf.fill([n], x[0]), [
        x[1]-n+i for i in range(n)]], axis=1)
    print(indices.get_shape())
    return indices


def testGatherND():
    # gather last 2 elements of (2, 5, 2), -> (2, 2, 2)
    # indices = np.asarray([[[0, 1], [0, 2]], [[1, 0], [1, 1]]])
    params = np.asarray([[['a0', 'b0'], ['c0', 'd0'], ['e0', 'f0'], ['g0', 'h0'], ['i0', 'j0']],
                         [['a1', 'b1'], ['c1', 'd1'], ['e1', 'f1'], ['g1', 'h1'], ['0', '0']]])
    batch = 2
    n = 2
    length = tf.placeholder(tf.int32, shape=[None])
    mapinput = tf.stack([tf.range(batch), length], axis=1)
    print("mapinput: {}".format(mapinput.get_shape()))
    indices = tf.map_fn(lambda x: getIndices(
        x, n), mapinput)
    # [tf.stack([tf.constant(b, shape=[batch]), [
    #                 s-n+i for i in range(n)]], axis=1) for b, s in enumerate(length)]
    sess = tf.InteractiveSession()
    gnd = tf.gather_nd(params, indices)
    i, r = sess.run([indices, gnd], feed_dict={length: [5, 4]})
    print(i)
    print(params.shape)
    print(r.shape)
    print("{}".format(r))


def testTensorShape():
    x = tf.placeholder(shape=[None, 16], dtype=tf.float32)
    d = tf.placeholder(shape=[], dtype=tf.float32)
    random_tensor = tf.random_uniform(tf.shape(x), dtype=tf.float32)
    print("random_tensor: {}".format(random_tensor.get_shape()))
    kept_idx = tf.greater_equal(random_tensor, 1.0 - d)
    print("kept_idx: {}".format(kept_idx.get_shape()))


def delayedFunc(i):
    return i+1, i*2, i**2


def testJoblib():
    r = Parallel(n_jobs=5)(delayed(delayedFunc)(i) for i in range(30))
    r1, r2, r3 = zip(*r)
    print("r1 ({}):{}".format(type(list(r1)), r1))
    print("r2:{}".format(r2))
    print("r3:{}".format(r3))


def testVariableScope():
    a = 3
    if 1 < 3:
        a = a+1
    else:
        a = a-1
    print(a)


def testTimeToBatch():
    inputs = tf.constant([[['a0', 'b0'], ['c0', 'd0'], ['e0', 'f0'], ['g0', 'h0'], ['i0', 'j0']],
                          [['a1', 'b1'], ['c1', 'd1'], ['e1', 'f1'], ['g1', 'h1'], ['0', '0']]])
    print(inputs.get_shape())
    ttb = time_to_batch(inputs, 2)
    print(ttb.get_shape())
    sess = tf.InteractiveSession()
    r = sess.run([ttb])
    print(r)


def testConv1d():
    # inputs = tf.constant([[[1, 0, 1],
    #                        [0, 1, 0],
    #                        [1, 0, 1],
    #                        [1, 1, 1],
    #                        [1, 1, 1]]], dtype=tf.float32)
    inputs = tf.constant([[[1],
                           [2],
                           [3],
                           [4],
                           [5]]], dtype=tf.float32)
    # kernel = tf.constant([[[6]],[[7]]], dtype=tf.float32)
    print("shape:{}".format(inputs.get_shape()))
    # c = tf.nn.conv1d(inputs, kernel, stride=1, padding='VALID')
    c = tf.layers.conv1d(inputs, filters=1, kernel_size=2, strides=1,
                         padding='VALID', use_bias=False)
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        out = sess.run([c])
        print(out)


def testInversePerm():
    x = tf.constant(
        [[3, 2, 1, 0], [2, 3, 0, 1]],
        dtype=tf.int32)
    with tf.Session() as sess:
        print(sess.run([tf.invert_permutation(x)]))


def testNestFlatten():
    x = tf.constant(
        [[3, 2, 1, 0], [2, 3, 0, 1]],
        dtype=tf.int32)
    with tf.Session() as sess:
        print(sess.run([tf.contrib.framework.nest.flatten(x)]))


def testReduceProdCumprod():
    x_h = tf.placeholder(tf.float32, [None, 2, 4])
    x = np.array(
        [[[3, 2, 1, 4], [2, 3, 4, 1]],
         [[4, 5, 6, 3], [5, 2, 1, 7]],
         [[5, 7, 8, 9], [6, 7, 3, 3]]],
        float
    )
    rp = tf.reduce_prod(x, [1])
    cp = tf.cumprod(x, 1, reverse=True)
    size = tf.shape(cp)[0]
    p1 = tf.range(tf.cast(size, tf.float32), dtype=tf.float32)
    p2 = tf.zeros([size], tf.float32)
    print("p1:{} p2:{}".format(p1.get_shape(), p2.get_shape()))
    mr = list(tf.map_fn(lambda p: (
        p[0], p[1]), (p1, p2), dtype=(tf.float32, tf.float32)))
    # print("map shape:{}".format(mr.get_shape()))
    indices = tf.stack(mr, 1)
    print(indices.get_shape())
    gcp = tf.gather_nd(cp, tf.cast(indices, tf.int32))
    with tf.Session() as sess:
        r1, r2, r3, idx = sess.run([rp, cp, gcp, indices], feed_dict={x_h: x})
        print("result of reduce_prod:\n{}".format(r1))
        print("result of cumprod:\n{}".format(r2))
        print("result of gathered cumprod:\n{}".format(r3))
        print("indices:\n{}".format(idx))


def testCosDecay():
    LEARNING_RATE = 1e-3
    LEARNING_RATE_ALPHA = 0.1
    LR_DECAY_STEPS = 10
    step = tf.placeholder(tf.int32, [])
    dlr = tf.train.cosine_decay_restarts(
        learning_rate=LEARNING_RATE,
        global_step=step,
        first_decay_steps=LR_DECAY_STEPS,
        t_mul=1.0,
        m_mul=1.0,
        alpha=LEARNING_RATE_ALPHA
    )
    with tf.Session() as sess:
        for i in range(100):
            print(sess.run([dlr], feed_dict={step: i+1000}))


def testFoldl():
    x_h = tf.placeholder(tf.int32, [None, 5])
    x = np.array(
        [[3, 4, 0, 2, 1],
         [2, 4, 3, 0, 1]]
    )
    fd = tf.foldl(
        lambda a, b: tf.stack(a, tf.invert_permutation(b)), x_h)
    with tf.Session() as sess:
        r = sess.run(fd, feed_dict={x_h: x})
        print(r)


def invert_permutation():
    x_h = tf.placeholder(tf.float32, [None, 5])
    x = np.array(
        [[3, 4, 0, 2, 1],
         [2, 1, 3, 4, 0]],
        float
    )
    dim = int(x_h.get_shape()[-1])
    size = tf.cast(tf.shape(x_h)[0], tf.float32)
    delta = tf.cast(tf.shape(x_h)[-1], tf.float32)
    rg = tf.range(0, size*delta, delta, dtype=tf.float32)
    rg = tf.reshape(rg, [-1, 1])
    rg = tf.tile(rg, [1, dim])
    x_a = tf.add(x_h, rg)
    flat = tf.reshape(x_a, [-1])
    iperm = tf.invert_permutation(tf.cast(flat, tf.int32))
    rs = tf.reshape(iperm, [-1, dim])
    rs_f = tf.subtract(rs, tf.cast(rg, tf.int32))
    with tf.Session() as sess:
        r_rg = sess.run(rg, feed_dict={x_h: x})
        print("rg:{}".format(r_rg))
        r = sess.run(flat, feed_dict={x_h: x})
        print(r)
        r_rs = sess.run(rs_f, feed_dict={x_h: x})
        print("final:\n{}".format(r_rs))
        check = sess.run(tf.invert_permutation([2, 1, 3, 4, 0]))
        print("check:\n{}".format(check))


def batch_gatcher():
    values = tf.constant(
        [[1, 2, 3, 4],
         [5, 6, 7, 8]]
    )
    indices = tf.constant(
        [[2, 3, 0, 1],
         [3, 1, 2, 0]]
    )
    idxf = tf.cast(indices, tf.float32)
    size = tf.shape(indices)[0]
    rg = tf.range(tf.cast(size, tf.float32), dtype=tf.float32)
    rg = tf.expand_dims(rg, -1)
    rg = tf.tile(rg, [1, int(indices.get_shape()[-1])])
    rg = tf.expand_dims(rg, -1)
    print("rg:{}".format(rg.get_shape()))
    idxf = tf.expand_dims(idxf, -1)
    print("idxf: {}".format(idxf.get_shape()))
    gidx = tf.concat([rg, idxf], -1)
    gidx = tf.cast(gidx, tf.int32)
    # target gidx: (2,2,2)
    # [[[0, 2], [0, 3], [0, 0], [0, 1]],
    #  [[1, 3], [1, 1], [1, 2], [1, 0]]]
    # target output:
    # [[3 4 1 2]
    # [8 6 7 5]]

    gn = tf.gather_nd(values, gidx)
    with tf.Session() as sess:
        r_rg, ridx, r = sess.run([rg, gidx, gn])

        print("r_rg:\n{}".format(r_rg))
        print("ridx:\n{}".format(ridx))
        print("r:\n{}".format(r))


def dynamicShape():
    x_h = tf.placeholder(tf.int32, [])
    x_p = tf.placeholder(tf.int32, [None])
    x_p.set_shape(tf.TensorShape([x_h]))

def reshape():
    c = tf.constant(
        [[2, 3, 4, 1],
         [3, 7, 5, 2]]
    )
    c = tf.reduce_prod(c)
    c1 = tf.reshape(c, [1])
    c2 = [tf.reduce_prod(c)]
    with tf.Session() as sess:
        out = sess.run([c1,c2])
        print(out[0])
        print(out[1])

# testGatherND()
# testGetFileName()
# print(__file__)
# f = __file__
# print(f[f.rindex('/')+1:f.rindex('.py')])

# testTensorShape()


# testJoblib()

# testVariableScope()


# testTimeToBatch()
# testConv1d()
# testInversePerm()
# testNestFlatten()
# testCosDecay()
# testReduceProdCumprod()
# testFoldl()
# dynamicShape()
# invert_permutation()
# batch_gatcher()
reshape()
