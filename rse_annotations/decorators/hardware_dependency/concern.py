"""@hardware_dependency: the result depends on the hardware it runs on (e.g. a GPU)."""
from .._base import Concern

TOKENS = ("cuda", "gpu", "tf.device", "torch.device", "jax.devices", "cupy",
          "set_memory_growth", "mixed_precision")


class HardwareDependency(Concern):
    def detect(self, v):
        hits = v.hits(TOKENS)
        if hits:
            return f"selects or uses an accelerator ({', '.join(hits[:2])})", "medium"
        return None


CONCERN = HardwareDependency(
    "hardware_dependency",
    "Are the device, driver and precision recorded, and does the result hold on other hardware?")
