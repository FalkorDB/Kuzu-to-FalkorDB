#!/usr/bin/env python3
"""
Graph Database to FalkorDB CSV Exporter

This script extracts all nodes and edges from Kuzu or LadybugDB databases and converts them
to FalkorDB-compatible CSV format. 

Usage:
    python3 kuzu_to_falkordb_export.py --db DATABASE_PATH --db-type {kuzu|ladybug} [--schema SCHEMA_FILE] [--output OUTPUT_DIR]

Features:
- Supports both Kuzu and LadybugDB databases
- Extracts all node types with proper FalkorDB formatting
- Extracts all edge types with source/target labels
- Creates FalkorDB-compatible CSV files
- Handles complex property types (lists, nested values)
- Generates schema documentation
- Auto-detects database type if not specified
"""

import os
import sys
import csv
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Database library imports - try both
KUZU_AVAILABLE = False
LADYBUG_AVAILABLE = False

try:
    import kuzu
    KUZU_AVAILABLE = True
except ImportError:
    pass

try:
    import ladybug as ladybugdb  # LadybugDB graph database
    LADYBUG_AVAILABLE = True
except ImportError:
    pass

if not KUZU_AVAILABLE and not LADYBUG_AVAILABLE:
    print("Error: No compatible graph database library found.")
    print("Install Kuzu with: pip3 install kuzu")
    print("Or install LadybugDB with: pip3 install ladybug-db")
    sys.exit(1)

class GraphToFalkorDBExporter:
    def __init__(self, db_path: str, db_type: str = None, schema_file: str = None, output_dir: str = "_csv_"):
        self.db_path = Path(db_path)
        self.schema_file = Path(schema_file) if schema_file else None
        self.output_dir = Path(output_dir)
        self.db_type = self._determine_db_type(db_type)
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        # Initialize database connection based on type
        if self.db_type == 'kuzu':
            if not KUZU_AVAILABLE:
                raise RuntimeError("Kuzu library not available. Install with: pip3 install kuzu")
            self.db = kuzu.Database(str(self.db_path))
            self.conn = kuzu.Connection(self.db)
        elif self.db_type == 'ladybug':
            if not LADYBUG_AVAILABLE:
                raise RuntimeError("LadybugDB library not available. Install with: pip3 install ladybug-db")
            # LadybugDB was formerly Kuzu, so it likely uses similar API
            # If the API is identical, we can use the same connection method
            try:
                self.db = ladybugdb.Database(str(self.db_path))
                self.conn = ladybugdb.Connection(self.db)
            except AttributeError:
                # Fallback: try using kuzu compatibility layer
                print("⚠️  LadybugDB detected but using Kuzu-compatible API")
                self.db = kuzu.Database(str(self.db_path))
                self.conn = kuzu.Connection(self.db)
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Schema information
        self.node_tables = {}
        self.relationship_tables = {}
        self.node_schemas = {}
        self.rel_schemas = {}
    
    def _determine_db_type(self, specified_type: str = None) -> str:
        """Determine database type from specification or auto-detection"""
        if specified_type:
            db_type = specified_type.lower()
            if db_type not in ['kuzu', 'ladybug']:
                raise ValueError(f"Invalid database type: {specified_type}. Must be 'kuzu' or 'ladybug'")
            return db_type
        
        # Auto-detect based on available libraries
        if KUZU_AVAILABLE and not LADYBUG_AVAILABLE:
            print("🔍 Auto-detected database type: Kuzu")
            return 'kuzu'
        elif LADYBUG_AVAILABLE and not KUZU_AVAILABLE:
            print("🔍 Auto-detected database type: LadybugDB")
            return 'ladybug'
        elif KUZU_AVAILABLE and LADYBUG_AVAILABLE:
            # Both available - default to Kuzu, but warn user
            print("⚠️  Both Kuzu and LadybugDB libraries detected. Defaulting to Kuzu.")
            print("   Use --db-type to specify explicitly.")
            return 'kuzu'
        else:
            raise RuntimeError("No compatible database library found")
        
    def discover_schema(self):
        """Discover all node and relationship tables in the database"""
        print("🔍 Discovering database schema...")
        
        # Get all distinct node labels
        try:
            result = self.conn.execute("MATCH (n) RETURN DISTINCT labels(n) AS label;")
            while result.has_next():
                label_str = result.get_next()[0]
                # Extract primary label (handle multiple labels)
                if label_str and '[' in label_str and ']' in label_str:
                    # Parse label array string like "[Application,Process]" 
                    labels = label_str.strip('[]').split(',')
                    primary_label = labels[0].strip() if labels else None
                else:
                    primary_label = label_str
                    
                if primary_label and primary_label not in self.node_tables:
                    self.node_tables[primary_label] = f"nodes_{primary_label}.csv"
                    # Discover schema for this node type
                    self.node_schemas[primary_label] = self.discover_node_schema(primary_label)
                    print(f"  📦 Found node table: {primary_label}")
        except Exception as e:
            print(f"  ⚠️  Error discovering nodes: {e}")
            
        # Discover all relationship types dynamically
        try:
            # In Kuzu, we need to use a different approach to get relationship types
            # Try to get table info from the system catalog
            result = self.conn.execute("CALL table_info('') RETURN *;")
            while result.has_next():
                row = result.get_next()
                # Look for relationship table names in the catalog
                if len(row) > 0 and isinstance(row[0], str):
                    table_name = row[0]
                    if not any(node_type.lower() in table_name.lower() for node_type in self.node_tables.keys()):
                        # This might be a relationship table
                        rel_type = table_name
                        if rel_type and rel_type not in self.relationship_tables:
                            # Map to FalkorDB edge type names
                            falkor_name = self._map_kuzu_to_falkordb_rel(rel_type)
                            self.relationship_tables[rel_type] = f"edges_{falkor_name}.csv"
                            print(f"  🔗 Found relationship table: {rel_type} -> {falkor_name}")
        except Exception as e:
            print(f"  ⚠️  Error with catalog query: {e}")
            # Fallback: try to discover relationships by sampling
            self._discover_relationships_by_sampling()
                
        print(f"  \u2713 Discovered {len(self.node_tables)} node types and {len(self.relationship_tables)} relationship types")
        
    def _discover_relationships_by_sampling(self):
        """Fallback method to discover relationships by trying common patterns"""
        print("    🔍 Trying fallback relationship discovery...")
        
        # Common relationship patterns to test
        test_patterns = [
            "CONNECTS", "CONTAINS", "DEPENDS_ON", "EXPOSES", "HOLDS", "INSTANCE", 
            "LISTENS", "PREVIOUS", "ROUTES", "RUNS", "TYPE", "VERSION",
            "HOSTS", "BELONGS_TO", "HAS", "USES", "LINKS",
            "CONNECTS_NET", "CONNECTS_INTERFACE", "CONTAINS_RACK", "CONTAINS_ROUTER",
            "DEPENDS_SERVICE", "DEPENDS_VERSION", "DEPENDS_SOFTWARE", 
            "HOLDS_MACHINE", "HOLDS_SWITCH", "INSTANCE_OS_VER", "INSTANCE_APP_SW",
            "INSTANCE_SVC_VER", "INSTANCE_SVC_SW", "LISTENS_APP", "LISTENS_SVC",
            "ROUTES_MACHINE", "ROUTES_SWITCH", "ROUTES_NETWORK", "ROUTES_ROUTER",
            "RUNS_OS", "RUNS_SVC", "RUNS_APP", "HAS_TYPE", "HAS_VERSION_SVC"
        ]
        
        for rel_type in test_patterns:
            try:
                # Try to find at least one relationship of this type
                result = self.conn.execute(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) LIMIT 1;")
                if result.has_next():
                    count = result.get_next()[0]
                    if count > 0:
                        falkor_name = self._map_kuzu_to_falkordb_rel(rel_type)
                        self.relationship_tables[rel_type] = f"edges_{falkor_name}.csv"
                        print(f"    ✓ Found relationship: {rel_type} ({count:,} instances) -> {falkor_name}")
            except Exception:
                # Relationship type doesn't exist, skip silently
                pass
        
    def _map_kuzu_to_falkordb_rel(self, kuzu_rel: str) -> str:
        """Map Kuzu relationship names to FalkorDB format with intelligent grouping"""
        # Convert to uppercase and normalize
        rel = kuzu_rel.upper().strip()
        
        # Pattern-based mapping for common relationship types
        if 'CONNECT' in rel:
            return 'CONNECTS'
        elif 'CONTAIN' in rel:
            return 'CONTAINS'
        elif 'DEPEND' in rel:
            return 'DEPENDS_ON'
        elif 'EXPOSE' in rel:
            return 'EXPOSES'
        elif 'HOLD' in rel:
            return 'HOLDS'
        elif 'HOST' in rel:
            return 'HOSTS'
        elif 'BELONG' in rel:
            return 'BELONGS_TO'
        elif 'INSTANCE' in rel:
            return 'INSTANCE'
        elif 'LISTEN' in rel:
            return 'LISTENS'
        elif 'PREVIOUS' in rel:
            return 'PREVIOUS'
        elif 'ROUTE' in rel:
            return 'ROUTES'
        elif 'RUN' in rel:
            return 'RUNS'
        elif 'TYPE' in rel or rel in ['HAS_TYPE', 'IS_TYPE']:
            return 'TYPE'
        elif 'VERSION' in rel:
            return 'VERSION'
        elif 'LINK' in rel:
            return 'LINKS'
        elif 'USE' in rel:
            return 'USES'
        elif rel == 'HAS':
            return 'HAS'
        else:
            # For unknown relationships, use the original name
            return rel
        
    def discover_node_schema(self, node_type: str) -> Dict[str, str]:
        """Discover schema for a specific node type by examining all properties"""
        schema = {"id": "INT64", "labels": "STRING"}  # Always include these
        
        try:
            # Get all property keys for this node type
            result = self.conn.execute(f"MATCH (n:{node_type}) RETURN keys(n) LIMIT 100;")
            all_keys = set()
            
            while result.has_next():
                keys_array = result.get_next()[0]
                if keys_array:
                    # Parse the keys array - format might be like "[key1, key2, key3]"
                    if isinstance(keys_array, str) and keys_array.startswith('['):
                        keys_str = keys_array.strip('[]')
                        if keys_str:
                            keys = [k.strip().strip('"') for k in keys_str.split(',')]
                            all_keys.update(keys)
                    elif isinstance(keys_array, list):
                        all_keys.update(keys_array)
            
            # Add discovered keys to schema (exclude 'id' as it's already included)
            for key in sorted(all_keys):
                if key and key != 'id':
                    schema[key] = "STRING"  # Default to string type
            
            print(f"    📋 Discovered {len(schema)} properties for {node_type}: {list(schema.keys())}")
            
        except Exception as e:
            print(f"    ⚠️  Could not discover full schema for {node_type}: {e}")
            # Fallback to basic schema
            schema["name"] = "STRING"
        
        return schema
        
    def export_nodes(self):
        """Export all node types to CSV files"""
        print(f"\n📤 Exporting {len(self.node_tables)} node types...")
        
        for node_type, filename in self.node_tables.items():
            print(f"  📦 Exporting {node_type}...")
            output_path = self.output_dir / filename
            
            try:
                # Build dynamic query based on discovered schema
                schema = self.node_schemas.get(node_type, {"id": "INT64", "labels": "STRING"})
                properties = list(schema.keys())
                
                # Build the query with all discovered properties
                property_selects = []
                for prop in properties:
                    if prop == 'labels':
                        property_selects.append("labels(n) AS labels")
                    else:
                        property_selects.append(f"n.{prop}")
                
                query = f"MATCH (n:{node_type}) RETURN {', '.join(property_selects)}"
                
                result = self.conn.execute(query)
                
                # Write CSV file
                rows_written = 0
                with open(output_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header based on discovered schema
                    writer.writerow(properties)
                    
                    while result.has_next():
                        row_data = result.get_next()
                        
                        # Process row data
                        processed_row = []
                        for value in row_data:
                            if value is None:
                                processed_row.append('')
                            else:
                                processed_row.append(str(value))
                        
                        writer.writerow(processed_row)
                        rows_written += 1
                
                print(f"    ✓ Exported {rows_written:,} {node_type} nodes to {filename}")
                
            except Exception as e:
                print(f"    ❌ Error exporting {node_type}: {e}")
                
        
    def export_relationships(self):
        """Export all relationship types to CSV files"""
        print(f"\n🔗 Exporting {len(self.relationship_tables)} relationship types...")
        
        # Group by FalkorDB edge type
        falkordb_edges = {}
        for kuzu_rel, filename in self.relationship_tables.items():
            falkor_type = self._map_kuzu_to_falkordb_rel(kuzu_rel)
            if falkor_type not in falkordb_edges:
                falkordb_edges[falkor_type] = []
            falkordb_edges[falkor_type].append(kuzu_rel)
        
        for falkor_type, kuzu_rels in falkordb_edges.items():
            print(f"  🔗 Exporting {falkor_type} (from {len(kuzu_rels)} Kuzu tables)...")
            output_path = self.output_dir / f"edges_{falkor_type}.csv"
            
            rows_written = 0
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['source', 'source_label', 'target', 'target_label', 'type'])
                
                for kuzu_rel in kuzu_rels:
                    try:
                        # Query relationships with source and target node information
                        query = f"""
                        MATCH (source)-[r:{kuzu_rel}]->(target) 
                        RETURN source.id, labels(source), target.id, labels(target), '{falkor_type}'
                        """
                        
                        result = self.conn.execute(query)
                        rel_count = 0
                        
                        while result.has_next():
                            row_data = result.get_next()
                            source_id = row_data[0]
                            source_label = self._extract_primary_label(row_data[1])
                            target_id = row_data[2]
                            target_label = self._extract_primary_label(row_data[3])
                            rel_type = row_data[4]
                            
                            # Add specific label mappings for different relationship contexts
                            source_label = self._enhance_label_context(source_label, kuzu_rel, 'source')
                            target_label = self._enhance_label_context(target_label, kuzu_rel, 'target')
                            
                            writer.writerow([source_id, source_label, target_id, target_label, rel_type])
                            rel_count += 1
                            
                        rows_written += rel_count
                        print(f"    ✓ Added {rel_count:,} {kuzu_rel} relationships")
                        
                    except Exception as e:
                        print(f"    ❌ Error exporting {kuzu_rel}: {e}")
            
            print(f"  ✓ Exported {rows_written:,} {falkor_type} relationships to edges_{falkor_type}.csv")
            
    def _extract_primary_label(self, label_str: str) -> str:
        """Extract primary label from Kuzu label string"""
        if not label_str:
            return "Unknown"
            
        # Handle array format like "[Application,Process]"
        if '[' in label_str and ']' in label_str:
            labels = label_str.strip('[]').split(',')
            return labels[0].strip() if labels else "Unknown"
        
        return str(label_str)
        
    def _enhance_label_context(self, label: str, kuzu_rel: str, direction: str) -> str:
        """Enhance labels with context for better FalkorDB compatibility"""
        # Pattern-based label enhancement for common cases
        rel_upper = kuzu_rel.upper()
        
        # For INSTANCE relationships
        if 'INSTANCE' in rel_upper:
            if direction == 'source':
                if 'Process' in label:
                    # Try to add more specific context based on the base label
                    if 'APPLICATION' in rel_upper or 'APP' in rel_upper:
                        return 'Application:Process'
                    elif 'SERVICE' in rel_upper or 'SVC' in rel_upper:
                        return 'Service:Process'
                    elif 'OS' in rel_upper:
                        return 'OS:Process'
            # For targets in INSTANCE relationships, preserve the original label
            # Kuzu already returns correct labels like 'SoftwareVersion' or 'Software'
            pass
        
        # For LISTENS relationships
        elif 'LISTEN' in rel_upper:
            if direction == 'source' and 'Process' in label:
                if 'APPLICATION' in rel_upper or 'APP' in rel_upper:
                    return 'Application:Process'
                elif 'SERVICE' in rel_upper or 'SVC' in rel_upper:
                    return 'Service:Process'
        
        # For RUNS relationships
        elif 'RUN' in rel_upper:
            if direction == 'target' and 'Process' in label:
                if 'OS' in rel_upper:
                    return 'OS:Process'
                elif 'APPLICATION' in rel_upper or 'APP' in rel_upper:
                    return 'Application:Process'
                elif 'SERVICE' in rel_upper or 'SVC' in rel_upper:
                    return 'Service:Process'
        
        # For CONNECTS relationships
        elif 'CONNECT' in rel_upper:
            if direction == 'target' and ('Network' in label or 'Zone' in label):
                return 'Network:Zone'
        
        # For TYPE relationships
        elif 'TYPE' in rel_upper:
            # Don't override - Kuzu already returns correct labels
            pass
        
        # For VERSION relationships
        elif 'VERSION' in rel_upper:
            if direction == 'source' and 'Software' in label:
                return 'Software:Service'
            # Don't override target labels - Kuzu already returns correct labels
        
        # Default: return original label
        return label
        
    def generate_schema_file(self):
        """Generate schema documentation file"""
        if self.schema_file:
            print(f"\n📄 Generating schema documentation: {self.schema_file}")
            
            schema_info = {
                "database": str(self.db_path),
                "export_timestamp": datetime.now().isoformat(),
                "node_types": len(self.node_tables),
                "relationship_types": len(self.relationship_tables),
                "nodes": dict(self.node_tables),
                "relationships": dict(self.relationship_tables)
            }
            
            try:
                with open(self.schema_file, 'w') as f:
                    json.dump(schema_info, f, indent=2)
                print(f"  ✓ Schema written to {self.schema_file}")
            except Exception as e:
                print(f"  ❌ Error writing schema: {e}")
                
    def run_export(self):
        """Run the complete export process"""
        print("🚀 Graph Database to FalkorDB CSV Exporter")
        print("=" * 50)
        print(f"Database Type: {self.db_type.upper()}")
        print(f"Database: {self.db_path}")
        print(f"Output: {self.output_dir}")
        if self.schema_file:
            print(f"Schema: {self.schema_file}")
        print("=" * 50)
        
        try:
            # Discover schema
            self.discover_schema()
            
            # Export nodes  
            self.export_nodes()
            
            # Export relationships
            self.export_relationships()
            
            # Generate schema file
            if self.schema_file:
                self.generate_schema_file()
                
            print(f"\n🎉 Export completed successfully!")
            print(f"📁 Output files in: {self.output_dir}")
            print(f"📊 Exported: {len(self.node_tables)} node types, {len(self.relationship_tables)} relationship types")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Export failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Export Kuzu or LadybugDB database to FalkorDB-compatible CSV format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Auto-detect database type
    python3 kuzu_to_falkordb_export.py --db network_it_smart_db
    
    # Specify Kuzu database
    python3 kuzu_to_falkordb_export.py --db network_it_smart_db --db-type kuzu
    
    # Specify LadybugDB database
    python3 kuzu_to_falkordb_export.py --db network_it_smart_db --db-type ladybug
    
    # Export with schema file
    python3 kuzu_to_falkordb_export.py --db network_it_smart_db --db-type kuzu --schema schema.json
    
    # Export to custom directory
    python3 kuzu_to_falkordb_export.py --db network_it_smart_db --output my_csv_export
        """
    )
    
    parser.add_argument("--db", "--database", 
                       required=True, 
                       help="Path to database file/directory")
    
    parser.add_argument("--db-type", "--type",
                       choices=['kuzu', 'ladybug'],
                       help="Database type: 'kuzu' or 'ladybug' (auto-detected if not specified)")
    
    parser.add_argument("--schema", 
                       help="Path to output schema JSON file (optional)")
    
    parser.add_argument("--output", 
                       default="_csv_",
                       help="Output directory for CSV files (default: _csv_)")
    
    args = parser.parse_args()
    
    try:
        exporter = GraphToFalkorDBExporter(
            db_path=args.db,
            db_type=args.db_type,
            schema_file=args.schema, 
            output_dir=args.output
        )
        
        success = exporter.run_export()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()