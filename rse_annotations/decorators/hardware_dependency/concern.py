"""@hardware_dependency: the result depends on the hardware it runs on (e.g. a GPU)."""
from .._base import Concern

TOKENS = ("cuda", "gpu", "tf.device", "torch.device", "jax.devices", "cupy",
          "set_memory_growth", "mixed_precision")


class HardwareDependency(Concern):
    assertion = "Device, driver and precision are recorded, and the result holds on other hardware."

    def detect(self, v):
        hits = v.hits(TOKENS)
        if hits:
            return f"selects or uses an accelerator ({', '.join(hits[:2])})", "medium"
        return None


CONCERN = HardwareDependency("hardware_dependency")
