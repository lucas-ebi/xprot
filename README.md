# X-Prot

X-Prot takes a multiple sequence alignment, a phylogenetic tree, a recipient representative
sequence to edit, and a donor tip identifying the clade to compare it against — their
most-recent-common-ancestor in the tree splits into the two subfamilies being compared. It
computes weighted residue conservation for each clade and changes the recipient representative,
column by column, wherever the donor clade has a conserved residue it doesn't already carry —
outputting the substitutions (and insertions, and optionally deletions), with the alignment,
per-position frequencies, and rule that produced each change. The donor side only needs a tip to
identify which clade plays that role: its own residues are never read, only its clade-wide
profile. See [Scientific background](#scientific-background) for the full method.

Every choice — the conservation threshold, the weighting scheme, literal vs. expanded mode — is a
plain function parameter with a default; runs are deterministic.

> [!NOTE]
> **Status: v0.2.0, working.** The analysis pipeline is an importable library (`xprot.core`:
> alignment/tree parsing, identifier mapping, Henikoff weights, weighted profiles and typicality,
> transformation-event generation, fixture comparison), `xprot.app.run_design`, which chains the
> whole pipeline behind one call, `xprot.render`'s deterministic output renderers, the `x-prot`
> command-line tool, and a browser UI (`app/`) running the same package in-browser as an
> installable, offline-capable PWA. Gate is green (`ruff`, `ruff format`, `mypy --strict`, tests);
> the browser UI is deployed and verified working on GitHub Pages. Not yet done: a contract test
> against an external reference alignment/tree.

## Install

```sh
git clone https://github.com/lucas-ebi/xprot.git
cd xprot                         # run every command below from the project root
uv sync --frozen --extra dev     # locked environment, canonical Python 3.11
uv run pytest
```

Without `uv` (still from the project root, after cloning):

```sh
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```sh
x-prot design \
  --alignment family.fasta --tree family.nwk \
  --recipient seqA --donor seqC \
  --out results/
```

The internal node is the most-recent-common-ancestor of `--recipient` and `--donor` in the tree;
the two subtrees containing them become the subfamilies (any unrelated sibling branches at a
polytomic ancestor are ignored). Add `--dry-run` to compute and print a one-line summary without
writing `results/`. On success, `--out` receives `transformed.fasta`, `events.tsv`, `events.json`,
`pairwise.txt`, `pairwise.json`, `summary.json`, and `diagnostics.json`.

### Browser UI

`app/` is a static site (no build step, no server) that runs the same package as the CLI, in a
Web Worker, via [Pyodide](https://pyodide.org):

```sh
python -m http.server     # from the repository root
```

then open `http://localhost:8000/app/`. Paste or upload an alignment and a tree, pick the
donor and recipient ids, and run — everything executes locally in the browser; nothing is
uploaded. The first run downloads the Python packages Pyodide needs; later runs use the browser
cache. Published on GitHub Pages from `/app` on `main`.

## Scientific background

X-Prot generalizes the evolution-based protein engineering approach that Lemos et al. (2024)
introduced and experimentally validated — computational modeling, molecular dynamics, and
enzymatic assays — on a transthyretin/5-hydroxyisourate hydrolase functional-switching case study,
into reusable, family-agnostic software: take a recipient representative and a donor tip, treat
the two subtrees under their most-recent-common-ancestor as a recipient and a donor subfamily, and
transfer the donor clade's conserved residues onto the recipient representative at the positions
where the two subfamilies diverge.

**Sequence weighting (Henikoff & Henikoff 1994).** Before any conservation is measured, every row
is weighted to reduce bias from over-represented sequence clusters. For sequence $i$ and alignment
column $j$, let $k(j)$ be the number of distinct states in column $j$ — the gap counts as a state
like any other — and $c(i,j)$ the count of the state sequence $i$ carries there. The weight is:

```math
w_i = \frac{1}{L} \sum_j \frac{1}{k(j)\cdot c(i,j)},
```

where $L$ is the alignment length. Because the gap is always one of the $k(j)$ states, every
column's contributions already sum to one, so this single $1/L$ gives $\sum_i w_i = 1$ with no
separate gap handling or renormalisation step.

**Weighted residue frequency.** For a subfamily $S$ (one of the two child clades) and column $j$,
the weighted frequency of state $r$ — a residue or the gap — is:

```math
f_{S,j}(r) = \frac{\sum_{i \in S,\ x_{i,j}=r} w_i}{D_{S,j}},
```

where $x_{i,j}$ is the state sequence $i$ carries at column $j$, and $D_{S,j}$ is by default the
subfamily's total weight ($\sum_{i \in S} w_i$); it can instead be restricted to the subfamily's
non-gap weight at that column only.

**Typicality.** A state is "typical" for a subfamily at a column when its weighted frequency
strictly exceeds a threshold $\theta$ (default $0.9$):

```math
\text{typical}_{S,j}(r) \iff f_{S,j}(r) > \theta.
```

In *expanded* mode the same test is applied to Taylor (1986) physicochemical classes instead of
individual residues, with $f_{S,j}(\text{class}) = \sum_{r\, \in\, \text{class}} f_{S,j}(r)$.

**Transformation.** At each alignment column, X-Prot proposes changing the recipient
representative's state to whichever state is typical for the donor subfamily:

```math
r \in \text{typical}_{donor,j}
```

The recipient subfamily's own conservation at that column plays no role in whether a candidate
exists — only in the ordinary case where the representative already carries the donor-typical
state, which is a no-op regardless. Multiple candidates (possible at a lower threshold) are ranked
by donor frequency. In expanded mode the same test runs over classes first: a class typical for
the donor, not already carried by the recipient's current residue, is expanded back into its
highest-frequency donor residue.

## References

- Lemos RP, Rodrigues JT, Portwood G, de Oliveira LC, Gomes dos Santos PH, Costa MAF, Pereira HD, Bleicher L, de Magalhães MTQ. (2024). Evolution-based protein engineering: functional switching between transthyretins and 5-hydroxyisourate hydrolases. *Journal of Biomolecular Structure and Dynamics*, 44(6), 3020–3036. <https://doi.org/10.1080/07391102.2024.2440647>
- Henikoff S, Henikoff JG. (1994). Position-based sequence weights. *J Mol Biol*, 243(4), 574–578. <https://doi.org/10.1016/0022-2836(94)90032-9>
- Taylor WR. (1986). The classification of amino acid conservation. *J Theor Biol*, 119(2), 205–218. <https://doi.org/10.1016/S0022-5193(86)80075-3>

## Citation

If you use this tool in your research, please cite Lemos et al. (2024) — see
[References](#references) — the paper that introduced and experimentally validated this
evolution-based protein engineering approach on a transthyretin/5-hydroxyisourate hydrolase case
study, which X-Prot generalizes into reusable software. The original module was developed by
**Lucas Carrijo de Oliveira** (<lucas@ebi.ac.uk>). You may also reference the repository directly:

```text
Lemos RP, Rodrigues JT, Portwood G, de Oliveira LC, Gomes dos Santos PH, Costa MAF, Pereira HD,
Bleicher L, de Magalhães MTQ. (2024). Evolution-based protein engineering: functional switching
between transthyretins and 5-hydroxyisourate hydrolases. Journal of Biomolecular Structure and
Dynamics, 44(6), 3020–3036. https://doi.org/10.1080/07391102.2024.2440647

Lucas C. de Oliveira. X-Prot. 2026.
https://github.com/lucas-ebi/xprot
```

## License

GNU General Public License v3 or later. See [LICENSE](LICENSE).
