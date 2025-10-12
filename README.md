# Kuzu to FalkorDB Migration

A 2 step process to migrate data from Kuzu graph database into FalkorDB.


## Overview

This tool bridges the gap between Kuzu and FalkorDB by automatically discovering your database schema and exporting all nodes and relationships to properly formatted CSV files that can be imported into FalkorDB.

In order to fully migrate, follow the documentation below to activate kuzu_to_falkordb_export.py to extract data from your current Kuzu graph database into csv files.
Next you can use FalkorDB Rust loader https://github.com/FalkorDB/FalkorDB-Loader-RS to load these CSV files directly into FalkorDB.

## Exporter Features

- **Automatic Schema Discovery**: Dynamically discovers all node types and relationship types in your Kuzu database
- **FalkorDB Compatibility**: Generates CSV files in the exact format expected by FalkorDB
- **Intelligent Label Mapping**: Maps Kuzu relationship names to standardized FalkorDB edge types
- **Complex Property Handling**: Properly handles lists, nested values, and various data types
- **Comprehensive Export**: Exports both nodes and relationships with full metadata
- **Schema Documentation**: Optional JSON schema file generation for documentation purposes

## Exporter Requirements

- Python 3.6+
- `kuzu` package

## Exporter Installation

1. Install the required dependencies:
```bash
pip3 install kuzu
```

2. Download the script:
```bash
git clone https://github.com/FalkorDB/Kuzu-to-FalkorDB.git
cd Kuzu-to-FalkorDB
```

## Exporter Usage

### Basic Usage

Export all data from a Kuzu database:
```bash
python3 kuzu_to_falkordb_export.py --db path/to/your/database
```

### Advanced Usage

```bash
# Export with schema documentation
python3 kuzu_to_falkordb_export.py --db network_it_smart_db --schema schema.json

# Export to custom directory
python3 kuzu_to_falkordb_export.py --db network_it_smart_db --output my_csv_export

# Full example with all options
python3 kuzu_to_falkordb_export.py --db network_it_smart_db --schema schema.json --output falkordb_import
```

### Command Line Options

| Option | Description | Required | Default |
|--------|-------------|----------|---------|
| `--db`, `--database` | Path to Kuzu database file/directory | Yes | - |
| `--schema` | Path to output schema JSON file | No | None |
| `--output` | Output directory for CSV files | No | `_csv_` |

## Exporter Output Structure

The script generates the following files:

### Node CSV Files
- `nodes_<NodeType>.csv`: One file per node type discovered
- Format: `id,labels,property1,property2,...`
- Example: `nodes_Application.csv`, `nodes_Machine.csv`

### Edge CSV Files
- `edges_<EdgeType>.csv`: One file per relationship type (grouped intelligently)
- Format: `source,source_label,target,target_label,type`
- Example: `edges_CONNECTS.csv`, `edges_CONTAINS.csv`

### Schema File (Optional)
- `schema.json`: Contains metadata about the export process
- Includes node types, relationship types, and file mappings

## Exporter Relationship Mapping

The script intelligently maps Kuzu relationship names to standardized FalkorDB edge types.

## Exporter Label Enhancement

The script enhances node labels with context for better FalkorDB compatibility:

- Process nodes in different contexts become `Application:Process`, `Service:Process`, or `OS:Process`
- Network zones become `Network:Zone`
- Service software becomes `Software:Service`

## Exporter Error Handling

The script includes robust error handling:
- Validates database path exists
- Handles missing relationship types gracefully
- Continues export even if individual tables fail
- Provides detailed progress and error messages

## Exporter Example Output

After running the script, you'll see output similar to:
```
🚀 Kuzu to FalkorDB CSV Exporter
==================================================
Database: network_it_smart_db
Output: _csv_
Schema: schema.json
==================================================

🔍 Discovering database schema...
  📦 Found node table: Application
  📦 Found node table: Machine
  🔗 Found relationship table: CONNECTS -> CONNECTS
  🔗 Found relationship table: INSTANCE_APP_SW -> INSTANCE
  ✓ Discovered 8 node types and 15 relationship types

📤 Exporting 8 node types...
  📦 Exporting Application...
    ✓ Exported 1,234 Application nodes to nodes_Application.csv

🔗 Exporting 15 relationship types...
  🔗 Exporting CONNECTS (from 3 Kuzu tables)...
    ✓ Exported 5,678 CONNECTS relationships to edges_CONNECTS.csv

🎉 Export completed successfully!
📁 Output files in: _csv_
📊 Exported: 8 node types, 15 relationship types
```

## Exporter Troubleshooting

### Common Issues

1. **Database not found**: Ensure the database path is correct and accessible
2. **Permission errors**: Check write permissions for the output directory
3. **Memory issues**: For very large databases, consider exporting in chunks

### Debug Mode

For additional debugging information, you can modify the script to include more verbose logging.

## License

[Add your license information here]

## Author

[Add author information here]
