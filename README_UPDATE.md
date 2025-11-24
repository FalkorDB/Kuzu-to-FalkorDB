# Graph Database to FalkorDB Migration Tool

**UPDATE**: This script now supports both **Kuzu** and **LadybugDB** databases!

## Overview

Export data from Kuzu or LadybugDB graph databases to FalkorDB-compatible CSV format.

## Supported Databases

- **Kuzu** - Embedded graph database
- **LadybugDB** - Graph database with object storage focus (formerly known as Kuzu)

## Installation

Install the required database library:

```bash
# For Kuzu databases
pip3 install kuzu

# For LadybugDB databases  
pip3 install ladybug-db

# Or install both
pip3 install kuzu ladybug-db
```

## Usage

### Auto-detect Database Type

The script will automatically detect which database library is available:

```bash
python3 kuzu_to_falkordb_export.py --db path/to/your/database
```

### Specify Database Type Explicitly

#### For Kuzu databases:
```bash
python3 kuzu_to_falkordb_export.py --db path/to/kuzu/db --db-type kuzu
```

#### For LadybugDB databases:
```bash
python3 kuzu_to_falkordb_export.py --db path/to/ladybug/db --db-type ladybug
```

### With Schema Output

```bash
python3 kuzu_to_falkordb_export.py --db path/to/database --db-type kuzu --schema schema.json
```

### Custom Output Directory

```bash
python3 kuzu_to_falkordb_export.py --db path/to/database --output my_export_folder
```

## Command-Line Options

```
--db DATABASE_PATH          Path to database file/directory (required)
--db-type {kuzu|ladybug}   Database type (auto-detected if not specified)
--schema SCHEMA_FILE       Path to output schema JSON file (optional)
--output OUTPUT_DIR        Output directory for CSV files (default: _csv_)
```

## Features

- ✅ **Dual Database Support**: Works with both Kuzu and LadybugDB
- ✅ **Auto-Detection**: Automatically detects available database library
- ✅ **Schema Discovery**: Automatically discovers node and relationship types
- ✅ **Smart Mapping**: Maps relationship types intelligently for FalkorDB
- ✅ **Label Enhancement**: Adds contextual labels for better graph semantics
- ✅ **CSV Export**: Generates FalkorDB-compatible CSV files

## Output Files

The script generates CSV files in the specified output directory:

- `nodes_<NodeType>.csv` - One file per node type
- `edges_<EdgeType>.csv` - One file per relationship type
- `schema.json` - (Optional) Schema documentation

## Notes on LadybugDB

**LadybugDB was formerly known as Kuzu**, so it maintains API compatibility. The script handles both:

1. **Native LadybugDB API** - If available, uses ladybug-specific methods
2. **Kuzu Compatibility Layer** - Falls back to Kuzu API if needed
3. **Automatic Detection** - Tries both methods automatically

If you have a LadybugDB database, the script will work seamlessly!

## Examples

### Example 1: Basic Kuzu Export
```bash
python3 kuzu_to_falkordb_export.py --db network_it_smart_db --db-type kuzu
```

### Example 2: LadybugDB with Schema
```bash
python3 kuzu_to_falkordb_export.py --db my_ladybug_db --db-type ladybug --schema schema.json
```

### Example 3: Auto-detect with Custom Output
```bash
python3 kuzu_to_falkordb_export.py --db my_database --output falkordb_import
```

## Troubleshooting

### "No compatible graph database library found"
- Install either `kuzu` or `ladybug-db` package
- Run: `pip3 install kuzu` or `pip3 install ladybug-db`

### "Both Kuzu and LadybugDB libraries detected"
- Both libraries are installed
- The script defaults to Kuzu
- Use `--db-type` to specify explicitly

### "Database not found"
- Check the database path exists
- Ensure you have read permissions
- Try using absolute path instead of relative

## License

See LICENSE file for details.
