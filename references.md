# References

## SOCP and SDP Relaxations of AC OPF

**Jabr (2006)** — Radial distribution load flow using conic programming. *IEEE Transactions on Power Systems*, 21(3), 1458–1459.
> Introduced the W-variable substitution and SOC relaxation for radial distribution networks. The origin of the lifted variable formulation used in `opfs.py`. Proves exactness on radial networks.

**Jabr (2007)** — A conic quadratic format for the load flow equations of meshed networks. *IEEE Transactions on Power Systems*, 22(4), 2285–2286.
> Extends the Jabr (2006) formulation to meshed transmission networks. Shows how the per-branch SOC constraint arises from the 2×2 principal submatrix of W, and discusses conditions under which the relaxation remains tight.

**Jabr (2008)** — Optimal power flow using an extended conic quadratic formulation. *IEEE Transactions on Power Systems*, 23(3), 1000–1008.
> Further extensions including generator cost curves and a broader class of network constraints within the conic framework.

**Lavaei & Low (2012)** — Zero duality gap in optimal power flow problem. *IEEE Transactions on Power Systems*, 27(1), 92–107.
> Proves that the SDP relaxation (full matrix $\mathbf{W} \succeq 0$) has zero duality gap under mild conditions on the network topology and cost structure. The theoretical foundation for why convex relaxations can recover global AC OPF optima. Highly cited.

**Low (2014)** — Convex relaxation of optimal power flow — Parts I & II. *IEEE Transactions on Control of Network Systems*, 1(1–2).
> The standard survey reference. Part I covers the SDP and SOCP relaxations with exactness proofs and connections to the Lavaei-Low result. Part II covers applications, extensions, and distributed algorithms. Read this after Jabr (2006) to get the full picture.

---

## Local Solutions and Duality Gaps

**Bukhsh, Grothey, McKinnon & Trodden (2013)** — Local solutions of the optimal power flow problem. *IEEE Transactions on Power Systems*, 28(4), 4780–4788.
> Catalogs small meshed test cases (WB2–WB5, case22loop) that have multiple local AC OPF optima and non-trivial SOCP duality gaps. WB5 and case22loop used in this project come from this paper. Shows concretely that SOCP can be non-exact on meshed networks even when all branch tightness ratios τ ≈ 1.

**Test case data files** — Local Optima in Optimal Power Flow. University of Edinburgh, School of Mathematics.
`https://webhomes.maths.ed.ac.uk/OptEnergy/LocalOpt/`
> Source of `WB5.m` and `case22loop.m` used in this project. Hosts MATPOWER-format case files for all cases in the Bukhsh et al. (2013) paper.

---

## Surveys and Textbook-Level Treatments

**Molzahn & Hiskens (2019)** — A survey of relaxations and approximations of the power flow equations. *Foundations and Trends in Electric Energy Systems*, 4(1–2).
> Comprehensive treatment of DC linearisation, SOCP, SDP, and moment/SOS relaxations in one place. Free on arXiv. The best single reference for understanding where the SOCP sits in the broader landscape of power flow approximations.
