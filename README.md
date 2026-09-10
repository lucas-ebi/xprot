# X-Prot

X-Prot takes a multiple sequence alignment, a phylogenetic tree, a chosen internal node, and one
representative sequence from each of that node's two child clades. It computes weighted residue
conservation for each clade, finds the positions where the clades are conserved differently, and
outputs the substitutions (and insertions, and optionally deletions) that change one
representative into a sequence carrying the other clade's conserved residues — with the alignment,
per-position frequencies, and rule that produced each change.

Conservation is measured with full-alignment Henikoff & Henikoff position-based weights, with the
gap treated as a state so the weights are normalised by construction. Per clade, a residue whose
weighted frequency strictly exceeds a threshold (default `0.9`) is "typical". In *expanded* mode the
same test is applied to Taylor physicochemical classes and a concrete donor residue is chosen from
the class. Every choice is a plain function parameter with a default; runs are deterministic.

**Status: early.** The analysis pipeline is implemented as an importable library
(`xprot.core`: alignment/tree parsing, identifier mapping, Henikoff weights, weighted profiles and
typicality, transformation-event generation, fixture comparison). Not yet built: the orchestration
layer, output rendering, the `x-prot` command-line tool, and a browser UI.

## Install

```sh
uv sync --frozen --extra dev     # locked environment, canonical Python 3.11
uv run pytest
```

Without `uv`:

```sh
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## References

- Lemos RP, Rodrigues JT, Portwood G, de Oliveira LC, Gomes dos Santos PH, Costa MAF, Pereira HD, Bleicher L, de Magalhães MTQ. (2024). Evolution-based protein engineering: functional switching between transthyretins and 5-hydroxyisourate hydrolases. *Journal of Biomolecular Structure and Dynamics*, 44(6), 3020–3036. <https://doi.org/10.1080/07391102.2024.2440647>
- Henikoff S, Henikoff JG. (1994). Position-based sequence weights. *J Mol Biol*, 243(4), 574–578. <https://doi.org/10.1016/0022-2836(94)90032-9>
- Taylor WR. (1986). The classification of amino acid conservation. *J Theor Biol*, 119(2), 205–218. <https://doi.org/10.1016/S0022-5193(86)80075-3>

## Citation

If you use this tool in your research, please cite the original software and the associated
publication (if any). The original module was developed by **Lucas Carrijo de Oliveira**
(<lucas@ebi.ac.uk>). For now, you may reference the repository directly:

```text
Lucas C. de Oliveira. X-Prot. 2026.
https://github.com/lucas-ebi/xprot
```

## License

GNU General Public License v3 or later. See [LICENSE](LICENSE).
