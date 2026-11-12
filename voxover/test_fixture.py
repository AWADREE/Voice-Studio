"""Synthetic non-personal prompt for tests; not a usable human voice."""
import tempfile
from pathlib import Path
import torch
_TEMP = tempfile.TemporaryDirectory(prefix="voxover-test-")
TEST_VOICE = Path(_TEMP.name)/"synthetic.pt"
torch.save({"items":[{"ref_spk_embedding":torch.zeros(2048),"ref_code":torch.zeros((8,16),dtype=torch.int64),"ref_text":"Synthetic test reference.","icl_mode":True,"x_vector_only_mode":False}]},TEST_VOICE)
