"""GRU4Rec model: Embedding -> GRU -> context vector.

The output projection to vocab-sized logits is NOT a Dense layer -- weights
and bias are plain trainable variables so tf.nn.sampled_softmax_loss can use
them directly during training, and full_logits() can use the same weights
for exact (non-sampled) scoring at evaluation/serving time. See
notebooks/02_model_prototype.ipynb for the full concept-by-concept
walkthrough of why the model is built this way.
"""

import tensorflow as tf


class GRU4Rec(tf.keras.Model):
    def __init__(self, vocab_size, embed_dim, gru_units, **kwargs):
        super().__init__(**kwargs)
        self.vocab_size = vocab_size
        self.embed_dim = embed_dim
        self.gru_units = gru_units
        self.embedding = tf.keras.layers.Embedding(vocab_size, embed_dim, mask_zero=True)
        self.gru = tf.keras.layers.GRU(gru_units)

    def build(self, input_shape):
        self.output_weights = self.add_weight(
            name="output_weights", shape=(self.vocab_size, self.gru_units),
            initializer="glorot_uniform",
        )
        self.output_bias = self.add_weight(
            name="output_bias", shape=(self.vocab_size,), initializer="zeros"
        )
        super().build(input_shape)

    def call(self, x, training=False):
        embedded = self.embedding(x)
        mask = self.embedding.compute_mask(x)
        return self.gru(embedded, mask=mask, training=training)  # (batch, gru_units) context vector

    def full_logits(self, context):
        """Exact scores over the full vocab -- only used for eval/serving,
        never inside the sampled-softmax training loop."""
        return tf.matmul(context, self.output_weights, transpose_b=True) + self.output_bias


def load_model(vocab_size, embed_dim, gru_units, max_seq_len, weights_path=None):
    """Construct a GRU4Rec and (optionally) restore saved weights.

    Always use this instead of `GRU4Rec(...)` + `model.build(input_shape)`
    when you intend to call `load_weights` afterward. `model.build(...)`
    alone only runs GRU4Rec's own `build()` override (output_weights/bias)
    -- the internal Embedding and GRU sublayers build themselves lazily on
    the first real forward pass, not on `build()`. Calling `load_weights`
    before that forward pass silently leaves the embedding table and GRU
    at random initialization while only the output layer restores
    correctly, since those variables don't exist yet for the checkpoint to
    fill in. The dummy forward pass below forces everything to build
    first, so the restore is complete.
    """
    model = GRU4Rec(vocab_size=vocab_size, embed_dim=embed_dim, gru_units=gru_units)
    model(tf.zeros((1, max_seq_len), dtype=tf.int64))
    if weights_path is not None:
        model.load_weights(weights_path)
    return model
