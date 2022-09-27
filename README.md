# universalizer

The KG-Hub Universalizer provides functions for knowledge graph cleanup and identifier normalization.

## Installation

Install with Poetry.
```
git clone https://github.com/Knowledge-Graph-Hub/universalizer.git
cd universalizer
poetry install
```

## Usage

With KGX format node and edge files in the same directory:

```
universalizer run path/to/directory
```

Or, if they're in a single tar.gz file:

```
universalizer run -c graph.tar.gz
```
