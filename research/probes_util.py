"""Small regression helpers shared by the probes (ridge and a random-Fourier-feature GP)."""
import numpy as np


def ridge_fit(X, Y, lam):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    Wt = np.linalg.solve(Z.T @ Z + lam * len(Z) * np.eye(Z.shape[1]), Z.T @ (Y - Y.mean(0)))
    return lambda Xn: ((Xn - mu) / sd) @ Wt + Y.mean(0)


def rff_gp_fit(X, Y, lam=1.0, n_feat=2000, seed=0):
    """GP regression with an RBF kernel approximated by random Fourier features (median-heuristic length scale)."""
    rng = np.random.default_rng(seed)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    sub = Z[rng.choice(len(Z), min(500, len(Z)), replace=False)]
    dist = np.sqrt(((sub[:, None] - sub[None]) ** 2).sum(-1))
    ls = np.median(dist[dist > 0])
    Wf = rng.standard_normal((Z.shape[1], n_feat)) / ls
    bf = rng.uniform(0, 2 * np.pi, n_feat)
    phi = lambda Zn: np.sqrt(2.0 / n_feat) * np.cos(Zn @ Wf + bf)
    P = phi(Z)
    Wt = np.linalg.solve(P.T @ P + lam * np.eye(n_feat), P.T @ (Y - Y.mean(0)))
    return lambda Xn: phi((Xn - mu) / sd) @ Wt + Y.mean(0)
