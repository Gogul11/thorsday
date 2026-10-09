# AgentOS Report Editing Guide

This guide explains how to edit, build, and maintain the AgentOS project report.

## Important files

- `authesis.tex` — Main document. Controls packages, chapter order, page settings, and included files.
- `1/Chapter1.tex` — Introduction.
- `2/Chapter2.tex` — Literature survey.
- `3/Chapter3.tex` — System design and architecture figures.
- `4/Chapter4.tex` — Implementation details, tables, and algorithms.
- `Appendix/appendix.tex` — Evaluation metrics and reporting protocol.
- `Conclusion/conclusion.tex` — Summary and future work.
- `References/references.tex` — IEEE-style references.
- `3/figures/` and `4/figures/` — Report diagrams and images.

## Editing text

Open the relevant `.tex` file and edit only the chapter content. Use LaTeX commands such as:

```latex
\section{Section Title}
\subsection{Subsection Title}
\textbf{Important text}
\emph{Emphasised text}
```

Escape special characters when necessary: `\%`, `\&`, `\_`, `\#`, and `\%`.

## Referencing figures, tables, and algorithms

Give every figure, table, and algorithm a label:

```latex
\caption{Short descriptive caption}
\label{fig:example}
```

Refer to it in the text before or near the object:

```latex
Figure~\ref{fig:example} shows the execution flow.
Table~\ref{tab:config} lists the configuration values.
Algorithm~\ref{alg:lifecycle} describes the lifecycle procedure.
```

Never type figure or table numbers manually because LaTeX updates numbering automatically.

## Adding or replacing a figure

Place the image in the correct `figures` folder, then use:

```latex
\begin{figure}[H]
\centering
\includegraphics[width=0.95\textwidth,keepaspectratio]{3/figures/example.pdf}
\caption{Descriptive figure caption}
\label{fig:example}
\end{figure}
```

For Graphviz diagrams, edit the corresponding `.dot` file and regenerate the PDF:

```powershell
& "C:\Program Files\Graphviz\bin\dot.exe" -Tpdf `
  3/figures/example.dot -o 3/figures/example.pdf
```

Keep diagrams inside the page margins and avoid cropping unless the crop values have been visually checked.

## Adding algorithms

Use the existing `algorithm` and `algpseudocode` style:

```latex
\begin{algorithm}[H]
\caption{Example Algorithm}
\label{alg:example}
\begin{algorithmic}[1]
\Require Input data
\Ensure Output data
\State Process the input
\State \Return the output
\end{algorithmic}
\end{algorithm}
```

Every algorithm must have a nearby textual reference.

## Editing references

Edit `References/references.tex`. Academic papers should include complete author names, publication details, and DOI where available. Online documentation should include:

```latex
[Online]. Available: \url{https://example.com} [Accessed: Oct. 9, 2026].
```

Do not add URLs to academic-paper entries when the report policy excludes them.

## Building the PDF on Windows

Open PowerShell in `report/BTECH_2026` and run:

```powershell
$env:Path = "C:\Users\curvy\AppData\Local\Programs\MiKTeX\miktex\bin\x64;" + $env:Path
pdflatex -interaction=nonstopmode -halt-on-error authesis.tex
pdflatex -interaction=nonstopmode -halt-on-error authesis.tex
```

Run LaTeX twice so the table of contents, list of figures, list of tables, algorithm numbers, and cross-references update correctly. The final file is `authesis.pdf`.

## Troubleshooting

- `??` in the PDF usually means a reference needs another LaTeX run.
- A figure is clipped: remove `trim` or reduce its width/height.
- A heading is stranded at the bottom of a page: add `\clearpage` before the section.
- A table overflows: use `tabularx`, reduce column widths, or shorten the text.
- Stale auxiliary files cause strange numbering: close LaTeX processes and remove generated `.aux`, `.toc`, `.lof`, `.lot`, `.loa`, and `.out` files, then compile twice.
- Warnings are acceptable only after checking that the PDF has no missing content, clipped figures, or unresolved references.

## Final checklist

1. Compile twice without a LaTeX error.
2. Check the table of contents and lists of figures and tables.
3. Check every figure, table, and algorithm is referenced in the text.
4. Check diagrams and tables do not cross the margins.
5. Review the final PDF page by page before submission.
