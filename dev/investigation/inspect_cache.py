import numpy as np
path = "components/knowledgebase/kb-manager/data/dense_embeddings.npz"
data = np.load(path)
print("Vectors shape:", data["vectors"].shape)
print("IDs length:", len(data["ids"]))
