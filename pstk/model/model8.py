from __future__ import print_function
import functools
import tensorflow as tf
import numpy as np
import math
from metrics import precision, recall
from model import lazy_property, numLayers, highway, dense_block, stddev
from cells import EGRUCell, EGRUCell_V1, EGRUCell_V2, LayerNormGRUCell, LayerNormNASCell, DenseCellWrapper, AlphaDropoutWrapper


class DRnnPredictorV1:
    '''
    Deep RNN + DNN predictor, with layer normalization
    '''

    def __init__(self, data, target, seqlen, classes, dropout, training, num_hidden=200, num_layers=1, learning_rate=1e-4):
        self.data = data
        self.target = target
        self.seqlen = seqlen
        self.dropout = dropout
        self.training = training
        self._num_hidden = num_hidden
        self._num_layers = num_layers
        self._classes = classes
        self._learning_rate = learning_rate
        self.precisions
        self.recalls
        self.f_score
        self.logits
        self.accuracy
        self.optimize
        self.cost
        self.one_hot
        self.worst

    def getName(self):
        return self.__class__.__name__

    @lazy_property
    def logits(self):
        layer = self.rnn(self, self.data)
        layer = self.dnn(self, layer)
        layer = tf.layers.dropout(
            inputs=layer, rate=0.1, training=self.training)
        output = tf.layers.dense(
            inputs=layer,
            units=len(self._classes),
            kernel_initializer=tf.truncated_normal_initializer(
                stddev=0.01),
            bias_initializer=tf.constant_initializer(0.1),
            activation=tf.nn.relu6,
            name="output"
        )
        return output

    @staticmethod
    def dnn(self, input):
        with tf.variable_scope("dnn"):
            dense = tf.layers.dense(
                inputs=input,
                units=self._num_hidden,
                kernel_initializer=tf.truncated_normal_initializer(
                    stddev=0.01),
                bias_initializer=tf.constant_initializer(0.1)
            )
            dense = tf.layers.dense(
                inputs=dense,
                units=self._num_hidden,
                kernel_initializer=tf.truncated_normal_initializer(
                    stddev=0.01),
                bias_initializer=tf.constant_initializer(0.1)
            )
            dense = tf.layers.dense(
                inputs=dense,
                units=self._num_hidden,
                kernel_initializer=tf.truncated_normal_initializer(
                    stddev=0.01),
                bias_initializer=tf.constant_initializer(0.1),
                activation=tf.nn.elu
            )
            return dense

    @staticmethod
    def rnn(self, input):
        # Deep Recurrent network.
        cells = []
        # Layer 1
        c = tf.nn.rnn_cell.GRUCell(
            num_units=self._num_hidden,
            kernel_initializer=tf.truncated_normal_initializer(
                stddev=0.01),
            bias_initializer=tf.constant_initializer(0.1)
        )
        cells.append(c)
        # Layer 2
        c = tf.contrib.rnn.LayerNormBasicLSTMCell(
            num_units=self._num_hidden
        )
        c = tf.contrib.rnn.HighwayWrapper(
            cell=c
        )
        cells.append(c)
        # Layer 3
        c = tf.contrib.rnn.UGRNNCell(
            num_units=self._num_hidden,
            initializer=tf.truncated_normal_initializer(
                stddev=0.01)
        )
        c = tf.contrib.rnn.HighwayWrapper(
            cell=c
        )
        cells.append(c)
        # Layer 4
        c = tf.contrib.rnn.NASCell(
            num_units=self._num_hidden
        )
        c = tf.contrib.rnn.HighwayWrapper(
            cell=c
        )
        cells.append(c)
        # Stack layers of cell
        mc = tf.nn.rnn_cell.MultiRNNCell(cells)
        output, _ = tf.nn.dynamic_rnn(
            mc,
            input,
            dtype=tf.float32,
            sequence_length=self.seqlen
        )
        return self.last_relevant(output, self.seqlen)

    @staticmethod
    def last_relevant(output, length):
        with tf.name_scope("last_relevant"):
            batch_size = tf.shape(output)[0]
            relevant = tf.gather_nd(output, tf.stack(
                [tf.range(batch_size), length-1], axis=1))
            return relevant

    @lazy_property
    def cost(self):
        return tf.reduce_mean(self.xentropy, name="cost")

    @lazy_property
    def optimize(self):
        return tf.train.AdamOptimizer(self._learning_rate).minimize(
            self.cost, global_step=tf.train.get_global_step())

    @lazy_property
    def xentropy(self):
        logits = self.logits
        with tf.name_scope("xentropy"):
            return tf.nn.softmax_cross_entropy_with_logits_v2(
                labels=self.target, logits=logits)

    @lazy_property
    def worst(self):
        logits = self.logits
        xentropy = self.xentropy
        with tf.name_scope("worst"):
            bidx = tf.argmax(xentropy)
            max_entropy = tf.reduce_max(xentropy)
            shift = len(self._classes)//2
            predict = tf.gather(tf.argmax(logits, 1), bidx)-shift
            actual = tf.argmax(tf.gather(self.target, bidx))-shift
            return bidx, max_entropy, predict, actual

    @lazy_property
    def accuracy(self):
        with tf.name_scope("accuracy"):
            accuracy = tf.equal(
                tf.argmax(self.target, 1), tf.argmax(self.logits, 1))
            return tf.reduce_mean(tf.cast(accuracy, tf.float32), name="accuracy")

    @lazy_property
    def one_hot(self):
        logits = self.logits
        size = len(self._classes)
        with tf.name_scope("one_hot"):
            return tf.one_hot(
                tf.argmax(logits, 1), size, axis=-1)

    @lazy_property
    def precisions(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Precisions"):
            ps = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                p, op = precision(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), p*100)
                ps.append(p)
                ops.append(op)
            return ps, ops

    @lazy_property
    def recalls(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Recalls"):
            rs = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                r, op = recall(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), r*100)
                rs.append(r)
                ops.append(op)
            return rs, ops

    @lazy_property
    def f_score(self):
        size = len(self._classes)
        mid = size // 2
        ps = self.precisions[0]
        rs = self.recalls[0]
        with tf.name_scope("Fscore"):
            ops = []
            for i, c in enumerate(self._classes):
                b = 2.0
                if i == mid:
                    b = 1.0
                elif i > mid:
                    b = 0.5
                p = ps[i]
                r = rs[i]
                nu = (1.+b**2.) * p * r
                de = (b**2. * p + r)
                op = tf.where(tf.less(de, 1e-7), de, nu/de)
                ops.append(op)
                tf.summary.scalar("c{}_{}".format(i, c), op*100)
            return ops


class DRnnPredictorV2:
    '''
    Deep RNN predictor, with layer normalization and highway connection
    '''

    def __init__(self, data, target, seqlen, classes, layer_width=200, num_rnn_layers=10, learning_rate=1e-3):
        self.data = data
        self.target = target
        self.seqlen = seqlen
        self._layer_width = layer_width
        self._num_rnn_layers = num_rnn_layers
        self._classes = classes
        self._learning_rate = learning_rate
        self.precisions
        self.recalls
        self.f_score
        self.logits
        self.accuracy
        self.optimize
        self.cost
        self.one_hot
        self.worst

    def getName(self):
        return self.__class__.__name__

    @lazy_property
    def logits(self):
        layer = self.rnn(self, self.data)
        output = tf.layers.dense(
            inputs=layer,
            units=len(self._classes),
            kernel_initializer=tf.truncated_normal_initializer(
                stddev=0.01),
            bias_initializer=tf.constant_initializer(0.1),
            activation=tf.nn.relu6,
            name="output"
        )
        return output

    @staticmethod
    def rnn(self, input):
        # Deep Recurrent network.
        cells = []
        feat_size = int(input.get_shape()[2])
        if feat_size != self._layer_width:
            # dimensionality transformation layer (no highway wrapper)
            c = tf.nn.rnn_cell.GRUCell(
                num_units=self._layer_width,
                kernel_initializer=tf.truncated_normal_initializer(
                    stddev=0.01),
                bias_initializer=tf.constant_initializer(0.1)
            )
            cells.append(c)
        carry_bias = math.e
        for i in range(self._num_rnn_layers):
            # Sub-Layer 1
            c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.NASCell(
                num_units=self._layer_width
            ), carry_bias_init=carry_bias)
            cells.append(c)
            # Sub-Layer 2
            c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.UGRNNCell(
                num_units=self._layer_width,
                initializer=tf.truncated_normal_initializer(
                    stddev=0.01)
            ), carry_bias_init=carry_bias)
            cells.append(c)
            # Sub-Layer 3
            if i % 2 != 0:
                c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.LayerNormBasicLSTMCell(
                    num_units=self._layer_width
                ), carry_bias_init=carry_bias)
                cells.append(c)
        # Stack layers of cell
        mc = tf.nn.rnn_cell.MultiRNNCell(cells)
        output, _ = tf.nn.dynamic_rnn(
            mc,
            input,
            dtype=tf.float32,
            sequence_length=self.seqlen
        )
        return self.last_relevant(output, self.seqlen)

    @staticmethod
    def last_relevant(output, length):
        with tf.name_scope("last_relevant"):
            batch_size = tf.shape(output)[0]
            relevant = tf.gather_nd(output, tf.stack(
                [tf.range(batch_size), length-1], axis=1))
            return relevant

    @lazy_property
    def cost(self):
        return tf.reduce_mean(self.xentropy, name="cost")

    @lazy_property
    def optimize(self):
        return tf.train.AdamOptimizer(self._learning_rate).minimize(
            self.cost, global_step=tf.train.get_global_step())

    @lazy_property
    def xentropy(self):
        logits = self.logits
        with tf.name_scope("xentropy"):
            return tf.nn.softmax_cross_entropy_with_logits_v2(
                labels=self.target, logits=logits)

    @lazy_property
    def worst(self):
        logits = self.logits
        xentropy = self.xentropy
        with tf.name_scope("worst"):
            bidx = tf.argmax(xentropy)
            max_entropy = tf.reduce_max(xentropy)
            shift = len(self._classes)//2
            predict = tf.gather(tf.argmax(logits, 1), bidx)-shift
            actual = tf.argmax(tf.gather(self.target, bidx))-shift
            return bidx, max_entropy, predict, actual

    @lazy_property
    def accuracy(self):
        with tf.name_scope("accuracy"):
            accuracy = tf.equal(
                tf.argmax(self.target, 1), tf.argmax(self.logits, 1))
            return tf.reduce_mean(tf.cast(accuracy, tf.float32), name="accuracy")

    @lazy_property
    def one_hot(self):
        logits = self.logits
        size = len(self._classes)
        with tf.name_scope("one_hot"):
            return tf.one_hot(
                tf.argmax(logits, 1), size, axis=-1)

    @lazy_property
    def precisions(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Precisions"):
            ps = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                p, op = precision(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), p*100)
                ps.append(p)
                ops.append(op)
            return ps, ops

    @lazy_property
    def recalls(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Recalls"):
            rs = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                r, op = recall(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), r*100)
                rs.append(r)
                ops.append(op)
            return rs, ops

    @lazy_property
    def f_score(self):
        size = len(self._classes)
        mid = size // 2
        ps = self.precisions[0]
        rs = self.recalls[0]
        with tf.name_scope("Fscore"):
            ops = []
            for i, c in enumerate(self._classes):
                b = 2.0
                if i == mid:
                    b = 1.0
                elif i > mid:
                    b = 0.5
                p = ps[i]
                r = rs[i]
                nu = (1.+b**2.) * p * r
                de = (b**2. * p + r)
                op = tf.where(tf.less(de, 1e-7), de, nu/de)
                ops.append(op)
                tf.summary.scalar("c{}_{}".format(i, c), op*100)
            return ops


class DRnnPredictorV3:
    '''
    Deep RNN + FCN predictor, with highway connection
    '''

    def __init__(self, data, target, seqlen, classes, layer_width=200, num_rnn_layers=10, num_fcn_layers=10, carry_bias=1.0, learning_rate=1e-3):
        self.data = data
        self.target = target
        self.seqlen = seqlen
        self._layer_width = layer_width
        self._num_rnn_layers = num_rnn_layers
        self._num_fcn_layers = num_fcn_layers
        self._classes = classes
        self._learning_rate = learning_rate
        self._carry_bias = carry_bias
        self.precisions
        self.recalls
        self.f_score
        self.logits
        self.accuracy
        self.optimize
        self.cost
        self.one_hot
        self.worst

    def getName(self):
        return self.__class__.__name__

    @lazy_property
    def logits(self):
        layer = self.rnn(self, self.data)
        layer = self.fcn(self, layer)
        output = tf.layers.dense(
            inputs=layer,
            units=len(self._classes),
            kernel_initializer=tf.truncated_normal_initializer(
                stddev=0.01),
            bias_initializer=tf.constant_initializer(0.1),
            activation=tf.nn.relu6,
            name="output"
        )
        return output

    @staticmethod
    def fcn(self, input):
        with tf.variable_scope("dnn"):
            # Dimensionality Abstraction
            # fc = tf.layers.dense(
            #     inputs=input,
            #     units=self._layer_width,
            #     kernel_initializer=tf.truncated_normal_initializer(
            #         stddev=0.01),
            #     bias_initializer=tf.constant_initializer(0.1),
            #     name="abstraction"
            # )
            fc = input
            p = round(math.sqrt(self._num_fcn_layers))
            for i in range(self._num_fcn_layers):
                activation = None
                if i > 0 and i % p == 0:
                    activation = tf.nn.elu
                fc = highway(
                    x=fc,
                    activation=activation,
                    carry_bias=-self._carry_bias
                )
            return fc

    @staticmethod
    def rnn(self, input):
        # Deep Recurrent network.
        cells = []
        carry_bias = self._carry_bias
        feat_size = int(input.get_shape()[2])
        # smooth layer
        c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.UGRNNCell(
            num_units=feat_size,
            forget_bias=carry_bias,
            initializer=tf.truncated_normal_initializer(stddev=0.01)
        ), carry_bias_init=carry_bias)
        cells.append(c)
        # dimensionality transformation layer (with or without highway)
        c = tf.contrib.rnn.NASCell(
            num_units=self._layer_width,
            use_biases=True
        )
        if feat_size == self._layer_width:
            c = tf.contrib.rnn.HighwayWrapper(c, carry_bias_init=carry_bias)
        cells.append(c)

        # minus one for prior and posterior cells
        for _ in range(self._num_rnn_layers-1):
            # Sub-Layer 1
            c = tf.contrib.rnn.HighwayWrapper(tf.nn.rnn_cell.GRUCell(
                num_units=self._layer_width,
                kernel_initializer=tf.truncated_normal_initializer(
                    stddev=0.01),
                bias_initializer=tf.constant_initializer(0.1)
            ), carry_bias_init=carry_bias)
            cells.append(c)
            # Sub-Layer 2
            c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.LayerNormBasicLSTMCell(
                num_units=self._layer_width
            ), carry_bias_init=carry_bias)
            cells.append(c)
            # Sub-Layer 3
            c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.NASCell(
                num_units=self._layer_width,
                use_biases=True
            ), carry_bias_init=carry_bias)
            cells.append(c)
            # Sub-Layer 4
            c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.UGRNNCell(
                num_units=self._layer_width,
                forget_bias=carry_bias,
                initializer=tf.truncated_normal_initializer(
                    stddev=0.01)
            ), carry_bias_init=carry_bias)
            cells.append(c)
        # Posterior cell
        c = tf.contrib.rnn.HighwayWrapper(tf.contrib.rnn.NASCell(
            num_units=self._layer_width,
            use_biases=True
        ), carry_bias_init=carry_bias)
        cells.append(c)
        # Stack layers of cell
        mc = tf.nn.rnn_cell.MultiRNNCell(cells)
        output, _ = tf.nn.dynamic_rnn(
            mc,
            input,
            dtype=tf.float32,
            sequence_length=self.seqlen
        )
        return self.last_relevant(output, self.seqlen)

    @staticmethod
    def last_relevant(output, length):
        with tf.name_scope("last_relevant"):
            batch_size = tf.shape(output)[0]
            relevant = tf.gather_nd(output, tf.stack(
                [tf.range(batch_size), length-1], axis=1))
            return relevant

    @lazy_property
    def cost(self):
        return tf.reduce_mean(self.xentropy, name="cost")

    @lazy_property
    def optimize(self):
        return tf.train.AdamOptimizer(self._learning_rate,
                                      epsilon=1e-7).minimize(
            self.cost, global_step=tf.train.get_global_step())

    @lazy_property
    def xentropy(self):
        logits = self.logits
        with tf.name_scope("xentropy"):
            return tf.nn.softmax_cross_entropy_with_logits_v2(
                labels=self.target, logits=logits)

    @lazy_property
    def worst(self):
        logits = self.logits
        xentropy = self.xentropy
        with tf.name_scope("worst"):
            bidx = tf.argmax(xentropy)
            max_entropy = tf.reduce_max(xentropy)
            shift = len(self._classes)//2
            predict = tf.gather(tf.argmax(logits, 1), bidx)-shift
            actual = tf.argmax(tf.gather(self.target, bidx))-shift
            return bidx, max_entropy, predict, actual

    @lazy_property
    def accuracy(self):
        with tf.name_scope("accuracy"):
            accuracy = tf.equal(
                tf.argmax(self.target, 1), tf.argmax(self.logits, 1))
            return tf.reduce_mean(tf.cast(accuracy, tf.float32), name="accuracy")

    @lazy_property
    def one_hot(self):
        logits = self.logits
        size = len(self._classes)
        with tf.name_scope("one_hot"):
            return tf.one_hot(
                tf.argmax(logits, 1), size, axis=-1)

    @lazy_property
    def precisions(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Precisions"):
            ps = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                p, op = precision(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), p*100)
                ps.append(p)
                ops.append(op)
            return ps, ops

    @lazy_property
    def recalls(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Recalls"):
            rs = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                r, op = recall(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), r*100)
                rs.append(r)
                ops.append(op)
            return rs, ops

    @lazy_property
    def f_score(self):
        size = len(self._classes)
        mid = size // 2
        ps = self.precisions[0]
        rs = self.recalls[0]
        with tf.name_scope("Fscore"):
            ops = []
            for i, c in enumerate(self._classes):
                b = 2.0
                if i == mid:
                    b = 1.0
                elif i > mid:
                    b = 0.5
                p = ps[i]
                r = rs[i]
                nu = (1.+b**2.) * p * r
                de = (b**2. * p + r)
                op = tf.where(tf.less(de, 1e-7), de, nu/de)
                ops.append(op)
                tf.summary.scalar("c{}_{}".format(i, c), op*100)
            return ops


class DRnnPredictorV4:
    '''
    Deep RNN + FCN predictor, with densenet connection, self-normalization
    '''

    def __init__(self, data, target, seqlen, classes, training, dropout,
                 layer_width=200, num_rnn_layers=10, rnn_layer_size=2, num_fcn_layers=10, size_decay=0.3, learning_rate=1e-3):
        self.data = data
        self.target = target
        self.seqlen = seqlen
        self._layer_width = layer_width
        self._num_rnn_layers = num_rnn_layers
        self._rnn_layer_size = rnn_layer_size
        self._num_fcn_layers = num_fcn_layers
        self._classes = classes
        self._learning_rate = learning_rate
        self._size_decay = size_decay
        self.training = training
        self.dropout = dropout
        self.precisions
        self.recalls
        self.f_score
        self.logits
        self.accuracy
        self.optimize
        self.cost
        self.one_hot
        self.worst

    def getName(self):
        return self.__class__.__name__

    @lazy_property
    def logits(self):
        layer = self.rnn(self, self.data)
        layer = self.fcn(self, layer)
        output = tf.layers.dense(
            inputs=layer,
            units=len(self._classes),
            kernel_initializer=tf.truncated_normal_initializer(
                stddev=stddev(1.0, int(layer.get_shape()[-1]))),
            bias_initializer=tf.constant_initializer(0.1),
            activation=tf.nn.selu,
            name="output"
        )
        return output

    @staticmethod
    def fcn(self, input):
        block = input
        with tf.variable_scope("fcn"):
            p = int(round(self._num_fcn_layers ** 0.5))
            for i in range(self._num_fcn_layers):
                with tf.variable_scope("dense_block_{}".format(i+1)):
                    if i % p == 0:
                        block = tf.contrib.layers.batch_norm(
                            inputs=block,
                            is_training=self.training,
                            updates_collections=None
                        )
                        if i > 0:
                            block = tf.nn.selu(block, name="selu")
                    block = dense_block(block, self._layer_width)
                    if i > 0 and i % p == 0:
                        block = tf.contrib.nn.alpha_dropout(
                            block, 1.0 - self.dropout)
                        size = int(block.get_shape()[-1])
                        new_size = int(round(size*self._size_decay))
                        block = tf.layers.dense(
                            inputs=block,
                            units=new_size,
                            kernel_initializer=tf.truncated_normal_initializer(
                                stddev=stddev(1.0, size)),
                            bias_initializer=tf.constant_initializer(0.1)
                        )
                        print("fcn layer_{} decayed size:{}".format(i, new_size))
                    else:
                        print("fcn layer_{} size:{}".format(
                            i, block.get_shape()[-1]))
            return block

    @staticmethod
    def rnn(self, input):
        # Deep Recurrent network.
        cells = []
        feat_size = int(input.get_shape()[-1])
        p = int(round(self._num_rnn_layers ** 0.35))
        output_size = self._layer_width + feat_size
        for i in range(self._num_rnn_layers):
            for j in range(self._rnn_layer_size):
                c = DenseCellWrapper(LayerNormGRUCell(
                    num_units=self._layer_width,
                    kernel_initializer=tf.truncated_normal_initializer(
                        stddev=stddev(1.0, feat_size)),
                    bias_initializer=tf.constant_initializer(0.1),
                    input_layer_norm=(not (i == 0 and j == 0))
                ), output_size=output_size)
                if not (i == 0 and j == 0):
                    c = AlphaDropoutWrapper(
                        c, input_keep_prob=1.0-self.dropout)
                output_size += self._layer_width
                cells.append(c)
            if i == 0 or i % p != 0:
                c = DenseCellWrapper(LayerNormNASCell(
                    num_units=self._layer_width,
                    use_biases=True,
                    input_layer_norm=True
                ), output_size=output_size)
                c = AlphaDropoutWrapper(c, input_keep_prob=1.0-self.dropout)
                output_size += self._layer_width
                print("rnn layer_{} size:{}".format(i, output_size))
                cells.append(c)
            else:
                size = int(round(output_size * self._size_decay))
                c = AlphaDropoutWrapper(LayerNormNASCell(
                    num_units=size,
                    use_biases=True,
                    input_layer_norm=True
                ), input_keep_prob=1.0-self.dropout)
                output_size = size
                print("rnn layer_{} decayed size:{}".format(i, output_size))
                cells.append(c)
        # Stack layers of cell
        mc = tf.nn.rnn_cell.MultiRNNCell(cells)
        output, _ = tf.nn.dynamic_rnn(
            mc,
            input,
            dtype=tf.float32,
            sequence_length=self.seqlen
        )
        return self.last_relevant(output, self.seqlen)

    @staticmethod
    def last_relevant(output, length):
        with tf.name_scope("last_relevant"):
            batch_size = tf.shape(output)[0]
            relevant = tf.gather_nd(output, tf.stack(
                [tf.range(batch_size), length-1], axis=1))
            return relevant

    @lazy_property
    def cost(self):
        return tf.reduce_mean(self.xentropy, name="cost")

    @lazy_property
    def optimize(self):
        return tf.train.AdamOptimizer(self._learning_rate,
                                      epsilon=1e-7).minimize(
            self.cost, global_step=tf.train.get_global_step())

    @lazy_property
    def xentropy(self):
        logits = self.logits
        with tf.name_scope("xentropy"):
            return tf.nn.softmax_cross_entropy_with_logits_v2(
                labels=self.target, logits=logits)

    @lazy_property
    def worst(self):
        logits = self.logits
        xentropy = self.xentropy
        with tf.name_scope("worst"):
            bidx = tf.argmax(xentropy)
            max_entropy = tf.reduce_max(xentropy)
            shift = len(self._classes)//2
            predict = tf.gather(tf.argmax(logits, 1), bidx)-shift
            actual = tf.argmax(tf.gather(self.target, bidx))-shift
            return bidx, max_entropy, predict, actual

    @lazy_property
    def accuracy(self):
        with tf.name_scope("accuracy"):
            accuracy = tf.equal(
                tf.argmax(self.target, 1), tf.argmax(self.logits, 1))
            return tf.reduce_mean(tf.cast(accuracy, tf.float32), name="accuracy")

    @lazy_property
    def one_hot(self):
        logits = self.logits
        size = len(self._classes)
        with tf.name_scope("one_hot"):
            return tf.one_hot(
                tf.argmax(logits, 1), size, axis=-1)

    @lazy_property
    def precisions(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Precisions"):
            ps = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                p, op = precision(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), p*100)
                ps.append(p)
                ops.append(op)
            return ps, ops

    @lazy_property
    def recalls(self):
        predictions = self.one_hot
        size = len(self._classes)
        with tf.name_scope("Recalls"):
            rs = []
            ops = []
            for i, c in enumerate(self._classes):
                mask = tf.one_hot([i], size, axis=-1)
                r, op = recall(
                    labels=self.target,
                    predictions=predictions,
                    weights=mask
                )
                tf.summary.scalar("c{}_{}".format(i, c), r*100)
                rs.append(r)
                ops.append(op)
            return rs, ops

    @lazy_property
    def f_score(self):
        size = len(self._classes)
        mid = size // 2
        ps = self.precisions[0]
        rs = self.recalls[0]
        with tf.name_scope("Fscore"):
            ops = []
            for i, c in enumerate(self._classes):
                b = 2.0
                if i == mid:
                    b = 1.0
                elif i > mid:
                    b = 0.5
                p = ps[i]
                r = rs[i]
                nu = (1.+b**2.) * p * r
                de = (b**2. * p + r)
                op = tf.where(tf.less(de, 1e-7), de, nu/de)
                ops.append(op)
                tf.summary.scalar("c{}_{}".format(i, c), op*100)
            return ops
