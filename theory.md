# SOCP Relaxation of AC OPF — Theory

## 1. The AC Optimal Power Flow Problem

The AC OPF seeks generator dispatches and bus voltages that minimise cost subject to the exact AC power flow equations and operating limits.

Each bus $i$ has a complex voltage $V_i = |V_i| e^{j\theta_i}$. The network is described by the admittance matrix $\mathbf{Y} = \mathbf{G} + j\mathbf{B}$, where $Y_{ij} = G_{ij} + jB_{ij}$.

The complex power injected at bus $i$ is:

$$S_i = V_i \sum_{k} Y_{ik}^* V_k^* = P_i + jQ_i$$

Expanding into real and imaginary parts using $V_i = |V_i|e^{j\theta_i}$:

$$P_i = \sum_{k} |V_i||V_k|\bigl(G_{ik}\cos\theta_{ik} + B_{ik}\sin\theta_{ik}\bigr)$$

$$Q_i = \sum_{k} |V_i||V_k|\bigl(G_{ik}\sin\theta_{ik} - B_{ik}\cos\theta_{ik}\bigr)$$

where $\theta_{ik} = \theta_i - \theta_k$.

The products $|V_i||V_k|\cos\theta_{ik}$ and $|V_i||V_k|\sin\theta_{ik}$ are bilinear and nonlinear in the decision variables — this is the source of non-convexity.

The full AC OPF is:

$$\min_{P_g,\, V,\, \theta} \quad \sum_{g} c_g P_g$$

$$\text{subject to:} \quad P_i = \sum_{g \in i} P_g - P_{\text{load},i}, \quad Q_i = \sum_{g \in i} Q_g - Q_{\text{load},i} \quad \forall i$$

$$V_{\min} \leq |V_i| \leq V_{\max}, \quad P_g^{\min} \leq P_g \leq P_g^{\max}, \quad Q_g^{\min} \leq Q_g \leq Q_g^{\max}$$

This is a non-convex, NP-hard problem in general. Local solvers (interior-point NLP) can find local optima but offer no global optimality certificate.

---

## 2. The Lifted W Variables

The key move is to eliminate the nonlinear terms by introducing a change of variables. Define:

$$W_{ii} = |V_i|^2, \qquad W_{ij} = V_i V_j^* \quad \text{for each branch } (i,j)$$

Write the off-diagonal entries in real and imaginary parts:

$$W_{ij} = W_{ij}^R + j W_{ij}^I, \qquad W_{ij}^R = \text{Re}(V_i V_j^*) = |V_i||V_j|\cos\theta_{ij}, \quad W_{ij}^I = \text{Im}(V_i V_j^*) = |V_i||V_j|\sin\theta_{ij}$$

The power injection equations become **linear** in the W variables:

$$P_i = G_{ii} W_{ii} + \sum_{k \neq i} \bigl(G_{ik} W_{ik}^R + B_{ik} W_{ik}^I\bigr)$$

$$Q_i = -B_{ii} W_{ii} + \sum_{k \neq i} \bigl(G_{ik} W_{ik}^I - B_{ik} W_{ik}^R\bigr)$$

This is the Jabr substitution. The power balance constraints are now linear — but we have introduced new variables $W_{ii}$, $W_{ij}^R$, $W_{ij}^I$ that must be constrained to actually correspond to physical voltages.

---

## 3. The Rank-1 Constraint

Collect all the W variables into a matrix. For an $N$-bus network define the $N \times N$ Hermitian matrix:

$$\mathbf{W} = \mathbf{V}\mathbf{V}^H, \qquad [\mathbf{W}]_{ij} = V_i V_j^*$$

The diagonal entries are $W_{ii} = |V_i|^2$ and the off-diagonals are $W_{ij} = V_i V_j^*$. Since $\mathbf{W}$ is an outer product of a vector with itself, it has **rank exactly 1**. Conversely, any positive semidefinite rank-1 matrix can be written as $\mathbf{V}\mathbf{V}^H$ for some complex vector $\mathbf{V}$.

So the AC OPF feasibility condition on the W variables is:

$$\mathbf{W} \succeq 0 \quad \text{and} \quad \text{rank}(\mathbf{W}) = 1$$

The positive semidefiniteness is convex. The rank constraint is not — it is the sole source of non-convexity in the W-variable formulation.

The **semidefinite relaxation (SDP)** drops the rank constraint entirely:

$$\mathbf{W} \succeq 0 \quad \text{(no rank constraint)}$$

This is convex and is the tightest known convex relaxation of the AC OPF. Its main drawback is computational cost: the SDP involves an $N \times N$ matrix variable, which scales poorly for large networks.

---

## 4. Deriving the SOC Constraint

The SOCP relaxation tightens the SDP on a branch-by-branch basis without maintaining the full matrix. Consider any single branch $(i, j)$ and extract the $2 \times 2$ principal submatrix of $\mathbf{W}$:

$$\mathbf{W}^{(ij)} = \begin{bmatrix} W_{ii} & W_{ij} \\ W_{ij}^* & W_{jj} \end{bmatrix} = \begin{bmatrix} |V_i|^2 & V_i V_j^* \\ V_j V_i^* & |V_j|^2 \end{bmatrix}$$

For a rank-1 matrix, any principal submatrix is also rank-1. So the physical constraint implies:

$$\text{rank}\bigl(\mathbf{W}^{(ij)}\bigr) = 1 \quad \Longleftrightarrow \quad \det\bigl(\mathbf{W}^{(ij)}\bigr) = 0$$

$$\det\bigl(\mathbf{W}^{(ij)}\bigr) = W_{ii} W_{jj} - W_{ij} W_{ij}^* = W_{ii} W_{jj} - |W_{ij}|^2 = 0$$

$$\Longleftrightarrow \quad |W_{ij}|^2 = W_{ii} W_{jj}$$

The **SOCP relaxation** replaces equality with inequality (dropping the rank-1 condition on this submatrix):

$$|W_{ij}|^2 \leq W_{ii} W_{jj}$$

This is exactly the Cauchy-Schwarz inequality $|\langle \mathbf{u}, \mathbf{v} \rangle|^2 \leq \|\mathbf{u}\|^2 \|\mathbf{v}\|^2$ applied to the complex inner product $\langle V_i, V_j \rangle$.

**Converting to standard SOC form.** The constraint $|W_{ij}|^2 \leq W_{ii} W_{jj}$ with $W_{ii}, W_{jj} \geq 0$ is equivalent to:

$$\left\| \begin{pmatrix} 2 W_{ij}^R \\ 2 W_{ij}^I \\ W_{ii} - W_{jj} \end{pmatrix} \right\|_2 \leq W_{ii} + W_{jj}$$

To see why, expand the left side squared:

$$4(W_{ij}^R)^2 + 4(W_{ij}^I)^2 + (W_{ii} - W_{jj})^2$$

and the right side squared:

$$(W_{ii} + W_{jj})^2$$

The inequality holds if and only if:

$$4|W_{ij}|^2 \leq (W_{ii} + W_{jj})^2 - (W_{ii} - W_{jj})^2 = 4 W_{ii} W_{jj}$$

$$\Longleftrightarrow \quad |W_{ij}|^2 \leq W_{ii} W_{jj} \qquad \checkmark$$

This is the rotated second-order cone form, which cvxpy and modern solvers handle natively and efficiently.

**Why is this the right relaxation?** The SOC per branch is:
1. A **necessary condition** for physical voltages (rank-1 implies SOC is tight)
2. **Convex** (second-order cone constraints are convex)
3. **Tractable** (one SOC per branch, scales linearly with network size)
4. **Tight on radial networks** (proven in Section 7)

The SDP is tighter but costs $O(N^3)$ per iteration. The SOCP costs $O(NL)$ and is the standard choice for large-scale AC OPF relaxations.

---

## 5. The Full SOCP Relaxation

Combining the lifted variables, linear power balance, and per-branch SOC constraints gives the SOCP relaxation:

**Decision variables:** $W_{ii} \geq 0$, $W_{ij}^R$, $W_{ij}^I$ (one per branch), $P_g$, $Q_g$ (per generator).

**Objective:**

$$\min \sum_{g} c_g P_g$$

**Voltage bounds:**

$$V_{\min}^2 \leq W_{ii} \leq V_{\max}^2 \quad \forall i, \qquad W_{\text{slack}} = V_{\text{slack}}^2$$

**Generator limits:**

$$P_g^{\min} \leq P_g \leq P_g^{\max}, \qquad Q_g^{\min} \leq Q_g \leq Q_g^{\max}$$

**Power balance (linear in W):**

$$G_{ii} W_{ii} + \sum_{k:(i,k) \in \mathcal{E}} \bigl(G_{ik} W_{ik}^R + B_{ik} W_{ik}^I\bigr) = \sum_{g \in i} P_g - P_{\text{load},i} \quad \forall i$$

$$-B_{ii} W_{ii} + \sum_{k:(i,k) \in \mathcal{E}} \bigl(G_{ik} W_{ik}^I - B_{ik} W_{ik}^R\bigr) = \sum_{g \in i} Q_g - Q_{\text{load},i} \quad \forall i$$

**SOC per branch:**

$$\left\| \begin{pmatrix} 2 W_{ij}^R \\ 2 W_{ij}^I \\ W_{ii} - W_{jj} \end{pmatrix} \right\|_2 \leq W_{ii} + W_{jj} \quad \forall (i,j) \in \mathcal{E}$$

**PV bus voltage setpoints (power flow mode only):**

$$W_{ii} = V_{i,\text{set}}^2 \quad \forall i \in \mathcal{V}_{\text{PV}}$$

In OPF mode, PV bus voltages are free within $[V_{\min}^2, V_{\max}^2]$ — fixing them to setpoints over-constrains the optimisation.

The SOCP feasible set is a **superset** of the AC OPF feasible set. Every AC-feasible operating point satisfies all SOCP constraints (SOC holds with equality), but not every SOCP-feasible point corresponds to physical voltages (SOC may hold strictly, or phases may be inconsistent across loops). As a result:

$$\text{SOCP objective} \leq \text{AC OPF objective}$$

The SOCP provides a **lower bound** on the true AC OPF cost. The gap between them is the **duality gap** or **relaxation gap**.

---

## 6. Branch Tightness

Define the **tightness ratio** for branch $k = (i, j)$:

$$\tau_k = \frac{|W_{ij}|^2}{W_{ii} \cdot W_{jj}} = \frac{(W_{ij}^R)^2 + (W_{ij}^I)^2}{W_{ii} \cdot W_{jj}} \in [0, 1]$$

- $\tau_k = 1$: the SOC constraint is **active** on this branch. The $2 \times 2$ submatrix $\mathbf{W}^{(ij)}$ has rank 1 — locally, $W_{ij}$ is consistent with some pair of physical voltages $V_i$, $V_j$.
- $\tau_k < 1$: the SOC is **slack**. $|W_{ij}|$ is strictly below its physical maximum $\sqrt{W_{ii} W_{jj}}$. No real voltage phasors can produce this $W_{ij}$ at these magnitudes.

$\tau_k < 1$ anywhere is a **certificate of inexactness**: the relaxation is provably non-tight on that branch, and the SOCP objective is strictly below the true AC OPF minimum.

$\tau_k = 1$ everywhere is a **necessary condition** for exactness — but not sufficient on meshed networks, as shown in Section 7.

In practice, solvers report $\tau_k$ slightly above or below 1 due to numerical tolerance. A threshold of $1 - \tau_k < 10^{-4}$ is typically treated as tight.

---

## 7. Loop Residuals and Meshed Networks

### Why $\tau = 1$ everywhere is not sufficient

Suppose $\tau_k = 1$ for every branch. Then for each branch $(i, j)$:

$$W_{ij} = \sqrt{W_{ii} W_{jj}} \cdot e^{j\phi_{ij}}$$

for some angle $\phi_{ij}$. In physical terms, $\phi_{ij}$ should equal $\theta_i - \theta_j$. The SOC constraint fixes the **magnitude** $|W_{ij}| = \sqrt{W_{ii} W_{jj}}$ but says nothing about the **phase** $\phi_{ij}$. The solver is free to assign each branch its own $\phi_{ij}$ independently.

On a **tree network**, this is harmless — there is only one path between any two buses, so no consistency check is needed.

On a **meshed network**, the phases must be mutually consistent around every cycle. Consider a triangle on buses 1, 2, 3:

$$\phi_{12} + \phi_{23} + \phi_{31} = 0 \pmod{2\pi}$$

because $(\theta_1 - \theta_2) + (\theta_2 - \theta_3) + (\theta_3 - \theta_1) = 0$. The SOCP never enforces this. Each $\phi_{ij}$ is set independently, and their sum around the loop can be nonzero — producing a W matrix with $\tau = 1$ everywhere that nonetheless does not correspond to any global set of voltage phasors.

### BFS spanning tree and loop detection

Given the SOCP solution $W_{ij}^R$, $W_{ij}^I$, recover angles by BFS from the slack bus:

1. Assign $\theta_{\text{slack}} = 0$.
2. For each tree edge $(i \to j)$ visited during BFS:

$$\theta_j = \theta_i - \arctan\!\left(\frac{W_{ij}^I}{W_{ij}^R}\right) = \theta_i - \phi_{ij}$$

3. Mark all tree edges. The remaining edges are **non-tree branches**, each closing exactly one fundamental cycle of the network graph.

### Loop residual definition

For each non-tree branch $k = (i, j)$, define:

$$\phi_{ij}^{\text{direct}} = \arctan\!\left(\frac{W_{ij}^I}{W_{ij}^R}\right) \qquad \text{(angle drop claimed by this branch's } W_{ij}\text{)}$$

$$\phi_{ij}^{\text{tree}} = \theta_i - \theta_j \qquad \text{(angle drop predicted by the BFS tree path from } i \text{ to } j\text{)}$$

$$\delta_k = \phi_{ij}^{\text{direct}} - \phi_{ij}^{\text{tree}} \quad \text{wrapped to } (-\pi, \pi]$$

$\delta_k$ is the **loop residual** for the fundamental cycle closed by branch $k$. It measures how much the SOCP solution's phase assignment around that cycle violates the physical constraint $\sum \theta_{ij} = 0$.

- $\delta_k = 0$: no phase inconsistency on this cycle; the W matrix is globally rank-1 around this loop.
- $\delta_k \neq 0$: the relaxation has drifted from the rank-1 manifold on this cycle. The SOCP solution is not achievable by any physical voltage phasor assignment.

The combination of tightness and residuals gives a complete picture:

| $\tau_k = 1$ everywhere | $\delta_k = 0$ for all loops | Interpretation |
|---|---|---|
| No | — | Provably inexact (slack SOC) |
| Yes | Yes | SOCP solution is AC-feasible; relaxation is exact |
| Yes | No | Inexact despite tight SOC — phase inconsistency across loops |

---

## 8. Exactness on Radial Networks

**Theorem (Jabr 2006, Low 2014):** On a radial (tree) network with no thermal branch limits, if the SOCP is feasible then its solution is AC-feasible and the relaxation is exact.

**Proof sketch.** A tree on $N$ buses has $N - 1$ branches. The BFS from the slack bus visits every bus exactly once, assigning a unique angle $\theta_i$ from the W solution. Because there are no non-tree branches, there are no loops and no loop residuals to check.

Given $\tau_k = 1$ for all $k$, the recovered phasors:

$$|V_i| = \sqrt{W_{ii}}, \qquad \angle V_i = \theta_i$$

satisfy $V_i V_j^* = W_{ij}$ for every branch $(i, j)$ by construction. The W matrix equals $\mathbf{V}\mathbf{V}^H$, which has rank 1. The SOCP solution is AC-feasible.

Since the SOCP feasible set contains the AC OPF feasible set, and the optimal SOCP solution is AC-feasible, the SOCP objective equals the AC OPF objective — there is no relaxation gap.

**Practical consequence.** Most distribution networks are operated radially. For these, the SOCP gives the **global** AC OPF optimum with the computational cost of a convex problem. This is the main practical motivation for the Jabr formulation.

**When exactness breaks on meshed networks.** The theorem fails when:

1. The network has cycles (non-tree branches exist and loop residuals can be nonzero).
2. Thermal branch limits are added as additional SOC constraints — these can introduce slack in the tightness even on radial networks.
3. The cost or network structure creates non-convex optimal faces (as in the WB5 case).

---

## 9. Example — WB5 Duality Gap

The WB5 network (Bukhsh et al. 2013) is a 5-bus meshed case with 6 lines designed to exhibit a non-trivial SOCP duality gap. Generator at Bus 1 costs \$4/MWh; generator at Bus 5 costs \$1/MWh. The cheap generator is connected to the rest of the network only via two high-impedance lines (L02-04, L03-05: $r = 0.55$, $x = 0.90$ pu), creating a non-convex bottleneck.

With loose voltage bounds $[0.5, 1.5]$ to allow convergence (the natural AC operating point has PQ bus voltages near 0.90 pu):

| Solver | Objective ($/h) | Note |
|---|---|---|
| DC OPF | 325 | Linear lower bound; ignores reactive power and losses |
| SOCP OPF | **740** | Convex lower bound; pushes Bus 5 voltage to 1.5 pu upper bound |
| AC OPF (pp.runopp) | **1256** | True AC local minimum |
| **Duality gap** | **515 (41%)** | SOCP is not exact here |

The SOCP solution has $\tau_k \approx 1$ at every branch (max gap $\approx 3 \times 10^{-9}$) — the SOC constraints are all active. Yet the loop residuals are $\delta_{L04\text{-}05} = 1.58°$ and $\delta_{L02\text{-}03} = 0.37°$. The SOCP exploits the freedom to assign inconsistent phases around the two fundamental cycles, reaching an objective that no physical voltage assignment can achieve.

This is the canonical illustration that $\tau_k = 1$ everywhere is necessary but not sufficient for exactness on meshed networks.

---

## 10. Multiple Operating Points in Ring Networks: The Loop Degree of Freedom

### 10.1 Why rings admit multiple AC solutions

A ring (cycle) on $N$ buses has $N$ branches but only needs $N - 1$ for a spanning tree. The one extra branch creates a single **fundamental cycle**. This cycle introduces a **loop degree of freedom**: the amount of power circulating around the ring is not uniquely determined by the bus injections.

In the **DC approximation** (linear, lossless), the loop flow is uniquely fixed once the minimum-spanning-tree voltage angles are assigned — the LP OPF resolves it unambiguously. In the **AC case** the nonlinear voltage–angle coupling allows multiple stable solutions for the same set of bus injections, each corresponding to a different power-flow circulation around the ring.

Formally, every AC power flow solution must satisfy the **phase-consistency constraint** around the ring:

$$\sum_{(i,j) \in \mathcal{C}} (\theta_i - \theta_j) = 0 \pmod{2\pi}$$

where $\mathcal{C}$ is the set of branches forming the ring. Because the per-branch angle drops $\theta_i - \theta_j$ depend nonlinearly on voltages and injections, this scalar equation can have multiple roots — each root is a distinct stable AC operating point.

The number of AC solutions grows with network complexity. For the 22-bus ring with one fundamental cycle, there are (at least) two qualitatively different AC power flow regimes corresponding to different patterns of power routing around the ring.

### 10.2 What the SOCP relaxes

The SOCP constrains each branch individually:

$$|W_{ij}|^2 \leq W_{ii} W_{jj}$$

This fixes the **magnitude** of each $W_{ij}$ but says nothing about the **phases** $\phi_{ij} = \arg(W_{ij})$. The solver assigns each branch its own phase freely. On the ring, the loop residual

$$\delta = \sum_{(i,j) \in \mathcal{C}} \phi_{ij} - 0$$

should be zero for any physically realizable voltage assignment, but the SOCP never enforces this. When $\delta \neq 0$, the relaxation has reached a point below the true AC feasible set.

For the 22-bus ring with **uniform costs** ($\$2$/MWh everywhere) the SOCP loop residual is exactly $0°$ — the optimal W matrix is globally rank-1 and the relaxation is exact. For the **asymmetric-cost** variant below the residual is $0.74°$ — also essentially zero, so the relaxation remains exact.

### 10.3 Asymmetric-cost variant: two distinct operating regimes

Assigning cheap costs ($\$1$/MWh) to the six generators on buses 1, 3, 5, 7, 9, 11 ("cheap arc") and expensive costs ($\$4$/MWh) to the five generators on buses 13, 15, 17, 19, 21 ("expensive arc") creates a cost structure that strongly favours one arc over the other.

The total load is $11 \times 204.25 = 2246.75$ MW. The six cheap generators can serve all of it — but only if power flows through the two boundary branches $L_{11\text{-}12}$ and $L_{22\text{-}01}$ from the cheap arc to the loads at buses 12–22. This routing requires much higher generator outputs at the boundary generators (Gen01 and Gen11) and drives large branch flows near the arc boundaries.

This creates two structurally different AC power flow solutions:

| | Balanced operating point | Globally optimal dispatch |
|---|---|---|
| Gen01 dispatch | ~229 MW | ~803 MW |
| Gen11 dispatch | ~204 MW | ~829 MW |
| Gen13–21 dispatch | ~204 MW each | **0 MW** (idle) |
| Min bus voltage | 0.977 pu | 0.953 pu |
| Total cost | **5336 $/h** | **2464 $/h** |
| Found by | NR from flat start | SOCP / pp.runopp |

The **balanced operating point** (5336 $/h) is a valid solution to the AC power flow equations when all non-slack generators are dispatched at their equal setpoints ($\approx 204$ MW). It is not a local minimum of the AC OPF — the interior-point solver (pp.runopp) moves away from it immediately. It is the natural operating point that Newton-Raphson converges to from a flat-start initialization.

The **globally optimal dispatch** (2464 $/h) has Gen01 and Gen11 carrying the full load of the expensive arc across the ring boundary. This is what the SOCP finds directly, and what any OPF solver finds regardless of starting point — there is a unique global optimum.

The cost difference is **2871 $/h (116%)** — a factor of 2 purely from choosing a better dispatch pattern. NR converges to the expensive operating point because it solves the power flow for fixed setpoints; it has no mechanism to search for a better dispatch.

### 10.4 SOCP diagnostics confirm exactness

For the asymmetric ring:

$$\max_k (1 - \tau_k) \approx 3 \times 10^{-12}, \qquad \max |\delta| = 0.74°$$

The tiny loop residual ($0.74° \approx 0.013$ rad) is numerical noise from the interior-point solver, not a genuine phase inconsistency. Since $\text{SOCP} = \text{pp.runopp} = 2464.49\ \$/\text{h}$ to four decimal places, the relaxation is exact: the globally optimal W matrix is rank-1 and corresponds to physical voltages.

This contrasts with **WB5**, where the loop residuals are $1.58°$ and $0.37°$ and the duality gap is $41\%$ — there the SOCP genuinely exploits phase freedom to reach a cost below any AC-feasible solution.

### 10.5 Practical lesson

The 22-bus asymmetric ring illustrates two separate ideas:

1. **Multiple AC-feasible operating points exist** for the same network and total load. NR initialized from balanced setpoints finds one; the globally optimal OPF finds another. The gap between them can be large (here, $2 \times$).

2. **SOCP is a reliable global optimizer** for this class of problems. On ring networks with canonical voltage limits and moderate impedances, the SOCP relaxation is exact ($\tau \approx 1$, $\delta \approx 0$), so its solution is both a lower bound and an AC-feasible solution — it is the global optimum.

The failure mode to watch for is WB5-style non-exactness, where the SOCP exploits phase freedom (large $\delta$) to reach a cost that is physically unachievable. Checking $\tau$ and $\delta$ after every SOCP solve tells you whether you have a certificate of global optimality or just a lower bound.

---

## References

- Jabr, R. A. (2006). Radial distribution load flow using conic programming. *IEEE Transactions on Power Systems*, 21(3), 1458–1459.
- Jabr, R. A. (2007). A conic quadratic format for the load flow equations of meshed networks. *IEEE Transactions on Power Systems*, 22(4), 2285–2286.
- Lavaei, J., & Low, S. H. (2012). Zero duality gap in optimal power flow problem. *IEEE Transactions on Power Systems*, 27(1), 92–107.
- Low, S. H. (2014). Convex relaxation of optimal power flow — Parts I & II. *IEEE Transactions on Control of Network Systems*, 1(1–2).
- Bukhsh, W. A., Grothey, A., McKinnon, K., & Trodden, P. (2013). Local solutions of the optimal power flow problem. *IEEE Transactions on Power Systems*, 28(4), 4780–4788.
- Molzahn, D. K., & Hiskens, I. A. (2019). A survey of relaxations and approximations of the power flow equations. *Foundations and Trends in Electric Energy Systems*, 4(1–2).
