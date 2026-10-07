import tensorflow as tf

from rse_annotations.decorators.markers import hardware_dependency


@hardware_dependency
def add_on_gpu():
    tf.config.set_soft_device_placement(False)   # no silent fallback to the CPU
    with tf.device("/GPU:0"):
        a = tf.constant([1.0, 2.0])
        b = tf.constant([3.0, 4.0])
        return tf.add(a, b)


if __name__ == "__main__":
    print(add_on_gpu())