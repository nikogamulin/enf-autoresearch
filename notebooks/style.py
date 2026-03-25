"""Consistent figure styling for Substack publication."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def apply_style():
    """Apply clean, Substack-friendly figure style."""
    plt.rcParams.update({
        # Figure
        'figure.facecolor': '#ffffff',
        'figure.edgecolor': '#ffffff',
        'figure.dpi': 150,
        
        # Axes
        'axes.facecolor': '#fafafa',
        'axes.edgecolor': '#cccccc',
        'axes.labelcolor': '#333333',
        'axes.titlecolor': '#1a1a1a',
        'axes.labelsize': 11,
        'axes.titlesize': 13,
        'axes.titleweight': 'bold',
        'axes.grid': True,
        'axes.spines.top': False,
        'axes.spines.right': False,
        
        # Grid
        'grid.color': '#e0e0e0',
        'grid.linewidth': 0.5,
        'grid.alpha': 0.7,
        
        # Text
        'text.color': '#333333',
        'font.family': 'sans-serif',
        'font.sans-serif': ['DejaVu Sans', 'Helvetica', 'Arial'],
        'font.size': 10,
        
        # Ticks
        'xtick.color': '#555555',
        'ytick.color': '#555555',
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        
        # Legend
        'legend.framealpha': 0.9,
        'legend.edgecolor': '#cccccc',
        'legend.fontsize': 9,
        
        # Lines
        'lines.linewidth': 1.5,
        
        # Savefig
        'savefig.facecolor': '#ffffff',
        'savefig.edgecolor': '#ffffff',
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.15,
    })

# Color palette - accessible, clean
COLORS = {
    'primary': '#2563eb',     # Blue
    'secondary': '#dc2626',   # Red
    'accent': '#059669',      # Green
    'warning': '#d97706',     # Amber
    'purple': '#7c3aed',
    'teal': '#0891b2',
    'gray': '#6b7280',
    'light_gray': '#d1d5db',
    
    # For year-coded charts
    '2023': '#059669',        # Green
    '2024': '#2563eb',        # Blue  
    '2025': '#dc2626',        # Red
    '2026': '#d97706',        # Amber
}

PALETTE = ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#0891b2', '#e11d48', '#65a30d']

def year_color(date_str):
    """Return color based on year in date string."""
    for year in ['2025', '2024', '2023', '2026']:
        if year in str(date_str):
            return COLORS[year]
    return COLORS['gray']
