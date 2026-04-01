import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import sys
import os


def _ensure_table(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _show_then_save(fig, output_png):
    fig.savefig(output_png)
    print(f"Plot saved to {output_png}")
    plt.close(fig)


def plot_l2_mshr_snapshot(db_path, output_png='l2_mshr_snapshot.png'):
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found")
        return

    # Connect to DB
    conn = sqlite3.connect(db_path)
    
    # Check if table exists
    if not _ensure_table(conn, 'L2MSHRSnapshotDB'):
        print("Error: Table L2MSHRSnapshotDB not found in database.")
        conn.close()
        return

    # Load data
    query = "SELECT STAMP, SITE, REQ_VALID, WAIT_GRANT, WAIT_RELEASEACK, WAIT_PPROBEACK, WAIT_RPROBEACK FROM L2MSHRSnapshotDB ORDER BY STAMP, SITE"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("Error: No data in L2MSHRSnapshotDB.")
        return

    # SITE is MSHR ID (0-15)
    df['SITE'] = pd.to_numeric(df['SITE'])
    
    # Determine state/color
    # States:
    # 0: invalid (REQ_VALID=0) -> White
    # 1: wait_grant -> Green
    # 2: wait_releaseack -> Red
    # 3: wait_pprobeack -> Blue
    # 4: wait_rprobeack -> Orange
    # 5: valid but no specific wait bit (other) -> Dark Gray
    
    def get_color_code(row):
        if row['REQ_VALID'] == 0:
            return 0 # White
        if row['WAIT_GRANT'] != 0:
            return 1 # Green
        if row['WAIT_RELEASEACK'] != 0:
            return 2 # Red
        if row['WAIT_PPROBEACK'] != 0:
            return 3 # Blue
        if row['WAIT_RPROBEACK'] != 0:
            return 4 # Orange
        return 5 # Valid/Other (Gray)

    df['color_code'] = df.apply(get_color_code, axis=1)

    # Pivot for plotting
    pivot_df = df.pivot(index='SITE', columns='STAMP', values='color_code')
    
    # Color mapping
    colors = ['#FFFFFF', '#00FF00', '#FF0000', "#008CFF", '#FFA500', "#2B2B2BFF"]
    cmap = ListedColormap(colors)

    fig, ax = plt.subplots(figsize=(20, 6))
    im = ax.imshow(pivot_df, aspect='auto', interpolation='nearest', cmap=cmap, origin='lower', vmin=0, vmax=5)

    # Labels
    ax.set_title('L2 MSHR Snapshot Timeline')
    ax.set_xlabel('Cycles (STAMP)')
    ax.set_ylabel('MSHR ID (SITE)')
    ax.set_yticks(range(16))
    
    # Legend
    labels = {
        'Invalid': colors[0],
        'Wait Grant': colors[1],
        'Wait ReleaseAck': colors[2],
        'Wait PProbeAck': colors[3],
        'Wait RProbeAck': colors[4],
        'Valid/Other': colors[5]
    }
    patches = [mpatches.Patch(color=v, label=k) for k, v in labels.items()]
    plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    
    _show_then_save(fig, output_png)


def plot_l3_mshr_snapshot(db_path, output_png='l3_mshr_snapshot.png'):
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found")
        return

    conn = sqlite3.connect(db_path)

    if not _ensure_table(conn, 'L3MSHRSnapshotDB'):
        print("Error: Table L3MSHRSnapshotDB not found in database.")
        conn.close()
        return

    query = "SELECT STAMP, SITE, VALID, CHANNEL FROM L3MSHRSnapshotDB ORDER BY STAMP, SITE"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("Error: No data in L3MSHRSnapshotDB.")
        return

    df['SITE'] = pd.to_numeric(df['SITE'])
    df['VALID'] = pd.to_numeric(df['VALID'])
    df['CHANNEL'] = pd.to_numeric(df['CHANNEL'])

    # States:
    # 0: invalid -> White
    # 1: Channel A -> Green (bit0)
    # 2: Channel B -> Blue  (bit1)
    # 3: Channel C -> Red   (bit2)
    # 4: valid but unknown channel -> Gray
    def get_l3_color_code(row):
        if row['VALID'] == 0:
            return 0

        channel = int(row['CHANNEL'])
        if channel & 0x1:
            return 1
        if channel & 0x2:
            return 2
        if channel & 0x4:
            return 3
        return 4

    df['color_code'] = df.apply(get_l3_color_code, axis=1)
    pivot_df = df.pivot(index='SITE', columns='STAMP', values='color_code')

    colors = ['#FFFFFF', '#00C853', '#2962FF', '#D50000', '#9E9E9E']
    cmap = ListedColormap(colors)

    fig, ax = plt.subplots(figsize=(22, 5))
    ax.imshow(pivot_df, aspect='auto', interpolation='nearest', cmap=cmap, origin='lower', vmin=0, vmax=4)

    ax.set_title('L3 MSHR Channel Snapshot Timeline')
    ax.set_xlabel('Cycles (STAMP)')
    ax.set_ylabel('MSHR ID (SITE)')
    ax.set_yticks(range(int(df['SITE'].min()), int(df['SITE'].max()) + 1))

    labels = {
        'Invalid': colors[0],
        'Channel A': colors[1],
        'Channel B': colors[2],
        'Channel C': colors[3],
        'Valid/Unknown': colors[4]
    }
    patches = [mpatches.Patch(color=v, label=k) for k, v in labels.items()]
    ax.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')

    ax.set_facecolor('#F5F5F5')
    ax.grid(False)
    plt.tight_layout()

    _show_then_save(fig, output_png)

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else 'tl-test-new/run/chiseldb.db'
    mode = sys.argv[2].lower() if len(sys.argv) > 2 else 'both'

    if mode == 'l2':
        plot_l2_mshr_snapshot(db)
    elif mode == 'l3':
        plot_l3_mshr_snapshot(db)
    elif mode == 'both':
        plot_l2_mshr_snapshot(db)
        plot_l3_mshr_snapshot(db)
    else:
        print("Usage: python3 plot_mshr.py <db_path> [l2|l3|both]")
