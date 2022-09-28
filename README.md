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

### ID and category mapping

SSSOM-format maps are supported. Use a single map file:

```
univeralizer run -m poro-mp-exact-1.0.sssom.tsv path/to/directory
```

or a whole directory of them:

```
univeralizer run -m path/to/mapfiles path/to/directory
```

For SSSOM maps from `subject_id` to `object_id`, subject node IDs will be remapped to object IDs.

If the `object_id` is a Biolink category ID, however, the node's category ID will be remapped instead of its URI.
