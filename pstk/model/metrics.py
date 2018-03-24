from __future__ import print_function
# from __future__ import absolute_import
# from __future__ import division


import tensorflow as tf

# pylint: disable-msg=E0611
from tensorflow.python.framework import ops
from tensorflow.python.framework import dtypes
from tensorflow.python.eager import context
from tensorflow.python.ops import variable_scope, math_ops, array_ops, confusion_matrix, control_flow_ops
from tensorflow.python.ops.metrics_impl import true_positives, true_negatives, false_negatives, false_positives, _remove_squeezable_dimensions


def recall(labels,
           predictions,
           weights=None,
           metrics_collections=None,
           updates_collections=None,
           name=None):
    """Computes the recall of the predictions with respect to the labels.

    The `recall` function creates two local variables, `true_positives`
    and `false_negatives`, that are used to compute the recall. This value is
    ultimately returned as `recall`, an idempotent operation that simply divides
    `true_positives` by the sum of `true_positives`  and `false_negatives`.

    For estimation of the metric over a stream of data, the function creates an
    `update_op` that updates these variables and returns the `recall`. `update_op`
    weights each prediction by the corresponding value in `weights`.

    If `weights` is `None`, weights default to 1. Use weights of 0 to mask values.

    Args:
      labels: The ground truth values, a `Tensor` whose dimensions must match
        `predictions`. Will be cast to `bool`.
      predictions: The predicted values, a `Tensor` of arbitrary dimensions. Will
        be cast to `bool`.
      weights: Optional `Tensor` whose rank is either 0, or the same rank as
        `labels`, and must be broadcastable to `labels` (i.e., all dimensions must
        be either `1`, or the same as the corresponding `labels` dimension).
      metrics_collections: An optional list of collections that `recall` should
        be added to.
      updates_collections: An optional list of collections that `update_op` should
        be added to.
      name: An optional variable_scope name.

    Returns:
      recall: Scalar float `Tensor` with the value of `true_positives` divided
        by the sum of `true_positives` and `false_negatives`.
      update_op: `Operation` that increments `true_positives` and
        `false_negatives` variables appropriately and whose value matches
        `recall`.

    Raises:
      ValueError: If `predictions` and `labels` have mismatched shapes, or if
        `weights` is not `None` and its shape doesn't match `predictions`, or if
        either `metrics_collections` or `updates_collections` are not a list or
        tuple.
      RuntimeError: If eager execution is enabled.
    """
    if context.in_eager_mode():
        raise RuntimeError('tf.metrics.recall is not supported is not '
                           'supported when eager execution is enabled.')

    with variable_scope.variable_scope(name, 'recall',
                                       (predictions, labels, weights)):
        predictions, labels, weights = _remove_squeezable_dimensions(
            predictions=math_ops.cast(predictions, dtype=dtypes.bool),
            labels=math_ops.cast(labels, dtype=dtypes.bool),
            weights=weights)

        true_p, true_positives_update_op = true_positives(
            labels,
            predictions,
            weights,
            metrics_collections=None,
            updates_collections=None,
            name=None)
        false_n, false_negatives_update_op = false_negatives(
            labels,
            predictions,
            weights,
            metrics_collections=None,
            updates_collections=None,
            name=None)

        def compute_recall(true_p, false_n, name):
            return array_ops.where(
                math_ops.greater(true_p + false_n, 0),
                math_ops.div(true_p, true_p + false_n), 0, name)

        update_op = compute_recall(true_positives_update_op,
                                   false_negatives_update_op, 'update_op')
        with tf.control_dependencies([update_op]):
            rec = compute_recall(true_p, false_n, 'value')

        if metrics_collections:
            ops.add_to_collections(metrics_collections, rec)

        if updates_collections:
            ops.add_to_collections(updates_collections, update_op)

        return rec, update_op


def precision(labels,
              predictions,
              weights=None,
              metrics_collections=None,
              updates_collections=None,
              name=None):
    """Computes the precision of the predictions with respect to the labels.

    The `precision` function creates two local variables,
    `true_positives` and `false_positives`, that are used to compute the
    precision. This value is ultimately returned as `precision`, an idempotent
    operation that simply divides `true_positives` by the sum of `true_positives`
    and `false_positives`.

    For estimation of the metric over a stream of data, the function creates an
    `update_op` operation that updates these variables and returns the
    `precision`. `update_op` weights each prediction by the corresponding value in
    `weights`.

    If `weights` is `None`, weights default to 1. Use weights of 0 to mask values.

    Args:
      labels: The ground truth values, a `Tensor` whose dimensions must match
        `predictions`. Will be cast to `bool`.
      predictions: The predicted values, a `Tensor` of arbitrary dimensions. Will
        be cast to `bool`.
      weights: Optional `Tensor` whose rank is either 0, or the same rank as
        `labels`, and must be broadcastable to `labels` (i.e., all dimensions must
        be either `1`, or the same as the corresponding `labels` dimension).
      metrics_collections: An optional list of collections that `precision` should
        be added to.
      updates_collections: An optional list of collections that `update_op` should
        be added to.
      name: An optional variable_scope name.

    Returns:
      precision: Scalar float `Tensor` with the value of `true_positives`
        divided by the sum of `true_positives` and `false_positives`.
      update_op: `Operation` that increments `true_positives` and
        `false_positives` variables appropriately and whose value matches
        `precision`.

    Raises:
      ValueError: If `predictions` and `labels` have mismatched shapes, or if
        `weights` is not `None` and its shape doesn't match `predictions`, or if
        either `metrics_collections` or `updates_collections` are not a list or
        tuple.
      RuntimeError: If eager execution is enabled.
    """
    if context.in_eager_mode():
        raise RuntimeError('tf.metrics.precision is not '
                           'supported when eager execution is enabled.')

    with variable_scope.variable_scope(name, 'precision',
                                       (predictions, labels, weights)):

        predictions, labels, weights = _remove_squeezable_dimensions(
            predictions=math_ops.cast(predictions, dtype=dtypes.bool),
            labels=math_ops.cast(labels, dtype=dtypes.bool),
            weights=weights)

        true_p, true_positives_update_op = true_positives(
            labels,
            predictions,
            weights,
            metrics_collections=None,
            updates_collections=None,
            name=None)
        false_p, false_positives_update_op = false_positives(
            labels,
            predictions,
            weights,
            metrics_collections=None,
            updates_collections=None,
            name=None)

        def compute_precision(tp, fp, name):
            return array_ops.where(
                math_ops.greater(tp + fp, 0), math_ops.div(tp, tp + fp), 0, name)

        update_op = compute_precision(true_positives_update_op,
                                      false_positives_update_op, 'update_op')
        with tf.control_dependencies([update_op]):
            p = compute_precision(true_p, false_p, 'value')

        if metrics_collections:
            ops.add_to_collections(metrics_collections, p)

        if updates_collections:
            ops.add_to_collections(updates_collections, update_op)

        return p, update_op
