from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
from datetime import datetime

class PlotPopup(QDialog):
    """
    Popup that shows live-updating historical plot for a component.
    """
    
    def __init__(self, title="Component Info", digital_twin=None, columns=None, 
                 current_state=None, parent=None, update_interval=1000):
        """
        Args:
            title: Title of the popup
            digital_twin: DigitalTwin instance for historical data
            columns: List of column names to plot (e.g., ['SOC', 'SOH'])
            current_state: Current State object with real-time values (not used currently)
            parent: Parent widget
            update_interval: Update interval in milliseconds (default 1000ms = 1 second)
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # Make non-modal so it stays open while data updates
        self.resize(900, 600)
        
        self.digital_twin = digital_twin
        self.columns = columns or []
        self.current_state = current_state
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Plot section
        if digital_twin and columns:
            self.canvas, self.ax = self._create_plot_widget()
            main_layout.addWidget(self.canvas)
            
            # Setup timer for live updates
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_plot)
            self.timer.start(update_interval)  # Update every second
        else:
            no_data_label = QLabel("No historical data available yet.\nStart a run to see plots.")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: gray; padding: 20px;")
            main_layout.addWidget(no_data_label)
            self.timer = None
    
    def closeEvent(self, event):
        """
        Stops timer when popup is closed.
        """
        if self.timer:
            self.timer.stop()
        super().closeEvent(event)
    
    def _get_unit(self, column):
        """
        Gets unit for a column.
        """
        units = {
            'SOC': '%',
            'SOH': '%',
            'Charging_Cycles': 'cycles',
            'Battery_Temp': '°C',
            'Motor_RPM': 'RPM',
            'Motor_Torque': 'Nm',
            'Motor_Temp': '°C',
            'Brake_Pad_Wear': '%',
            'Charging_Voltage': 'V',
            'Tire_Pressure': 'PSI',
            'DTC': ''
        }
        return units.get(column, '')
    
    def _create_plot_widget(self):
        """
        Creates matplotlib plot widget with subplots.
        """
        # Create matplotlib figure with subplots (one per parameter)
        num_plots = len(self.columns)
        fig = Figure(figsize=(10, 2.5 * num_plots), dpi=100)
        canvas = FigureCanvas(fig)
        
        # Apply professional styling
        fig.patch.set_facecolor('#FAFAFA')
        
        # Create subplots, one for each parameter
        self.axes = []
        for i in range(num_plots):
            ax = fig.add_subplot(num_plots, 1, i + 1)
            self.axes.append(ax)
            
            # Style each subplot
            ax.set_facecolor('white')
            ax.grid(True, alpha=0.3, color='#E0E0E0', linestyle='-', linewidth=0.8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#BDBDBD')
            ax.spines['bottom'].set_color('#BDBDBD')
        
        fig.tight_layout(pad=2.0)
        
        return canvas, self.axes
    
    def _update_plot(self):
        """
        Update the plot with latest data from digital twin.
        """
        if not self.digital_twin or not hasattr(self, 'axes'):
            return
        
        df = self.digital_twin.historical_dataset
        
        if df.empty:
            return
        
        # Convert timestamp to datetime
        df_plot = df.copy()
        if 'TimeStamp' in df_plot.columns:
            try:
                df_plot['TimeStamp'] = pd.to_datetime(df_plot['TimeStamp'])
            except:
                pass
        
        # Color scheme for EV Digital Twin
        colors = {
            'SOC': '#2196F3',           # Blue
            'SOH': '#4CAF50',           # Green
            'Battery_Temp': '#FF9800',  # Orange
            'Motor_RPM': '#2196F3',     # Blue
            'Motor_Torque': '#9C27B0',  # Purple
            'Motor_Temp': '#FF9800',    # Orange
            'Tire_Pressure': '#2196F3', # Blue
            'Brake_Pad_Wear': '#F44336' # Red
        }
        
        # Update each subplot
        for idx, col in enumerate(self.columns):
            if col not in df_plot.columns or idx >= len(self.axes):
                continue
            
            ax = self.axes[idx]
            ax.clear()
            
            # Get color for this parameter
            color = colors.get(col, '#2196F3')
            
            # Apply lookback window (show last 7 days max)
            df_col = self._apply_lookback_window(df_plot, 'TimeStamp')
            
            # Plot the data
            ax.plot(df_col['TimeStamp'], df_col[col], 
                   color=color, linewidth=2.5, marker='o', 
                   markersize=3, markerfacecolor=color, 
                   markeredgecolor='white', markeredgewidth=0.5)
            
            # Styling
            unit = self._get_unit(col)
            ax.set_ylabel(f'{col.replace("_", " ")}\n({unit})', 
                         fontsize=11, fontweight='bold', color='#424242')
            
            # Only show x-label on bottom plot
            if idx == len(self.columns) - 1:
                ax.set_xlabel('Time', fontsize=11, fontweight='bold', color='#424242')
                ax.tick_params(axis='x', rotation=45, labelsize=9)
            else:
                ax.set_xticklabels([])
            
            ax.tick_params(axis='y', labelsize=10)
            ax.grid(True, alpha=0.3, color='#E0E0E0', linestyle='-', linewidth=0.8)
            
            # Style spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#BDBDBD')
            ax.spines['bottom'].set_color('#BDBDBD')
            
            # Add current value annotation
            if len(df_col) > 0:
                last_value = df_col[col].iloc[-1]
                ax.text(0.02, 0.95, f'Current: {last_value:.1f} {unit}',
                       transform=ax.transAxes, fontsize=10,
                       verticalalignment='top', fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='white', 
                                alpha=0.8, edgecolor=color, linewidth=2))
        
        # Update main title with total points and window info
        window_info = ""
        if len(df) > 0:
            time_span = (df_plot['TimeStamp'].iloc[-1] - df_plot['TimeStamp'].iloc[0]).total_seconds() / 3600
            if time_span >= 24:
                window_info = f" - Last {time_span/24:.1f} days"
            else:
                window_info = f" - Last {time_span:.1f} hours"
        
        self.setWindowTitle(f'{self.windowTitle().split(" (")[0]} ({len(df)} points{window_info})')
        self.canvas.draw()
    
    def _apply_lookback_window(self, df, timestamp_col, lookback_days=7):
        """
        Apply lookback window - keep only last N days of data.
        
        Args:
            df: DataFrame with timestamp column
            timestamp_col: Name of timestamp column
            lookback_days: Number of days to keep (default 7)
        
        Returns:
            Filtered DataFrame with only recent data
        """
        if df.empty or timestamp_col not in df.columns:
            return df
        
        # Get the latest timestamp
        latest_time = df[timestamp_col].iloc[-1]
        
        # Calculate cutoff time (N days ago)
        cutoff_time = latest_time - pd.Timedelta(days=lookback_days)
        
        # Filter data
        filtered_df = df[df[timestamp_col] >= cutoff_time].copy()
        
        return filtered_df
    
    def _add_threshold_lines(self, ax, column, y_min, y_max):
        """
        Adds warning/danger threshold lines to plot.
        """
        thresholds = {
            'SOC': {'warning': 30, 'danger': 20, 'type': 'min'},
            'Battery_Temp': {'warning': 45, 'danger': 55, 'type': 'max'},
            'Motor_Temp': {'warning': 80, 'danger': 90, 'type': 'max'},
            'Tire_Pressure': {'warning_low': 28, 'danger_low': 25, 
                            'warning_high': 38, 'danger_high': 42, 'type': 'range'},
            'Brake_Pad_Wear': {'warning': 70, 'danger': 85, 'type': 'max'}
        }
        
        if column not in thresholds:
            return
        
        thresh = thresholds[column]
        
        # Draw threshold lines
        if thresh['type'] == 'min':
            if 'warning' in thresh:
                ax.axhline(y=thresh['warning'], color='#FF9800', 
                          linestyle='--', linewidth=1.5, alpha=0.7, 
                          label=f"Warning < {thresh['warning']}")
            if 'danger' in thresh:
                ax.axhline(y=thresh['danger'], color='#F44336', 
                          linestyle='--', linewidth=1.5, alpha=0.7,
                          label=f"Danger < {thresh['danger']}")
        
        elif thresh['type'] == 'max':
            if 'warning' in thresh:
                ax.axhline(y=thresh['warning'], color='#FF9800', 
                          linestyle='--', linewidth=1.5, alpha=0.7,
                          label=f"Warning > {thresh['warning']}")
            if 'danger' in thresh:
                ax.axhline(y=thresh['danger'], color='#F44336', 
                          linestyle='--', linewidth=1.5, alpha=0.7,
                          label=f"Danger > {thresh['danger']}")
        
        elif thresh['type'] == 'range':
            if 'warning_low' in thresh:
                ax.axhline(y=thresh['warning_low'], color='#FF9800', 
                          linestyle='--', linewidth=1.5, alpha=0.7)
            if 'warning_high' in thresh:
                ax.axhline(y=thresh['warning_high'], color='#FF9800', 
                          linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Add legend only if threshold lines were actually drawn
        # Check if any handles/labels exist (threshold lines create them)
        handles, labels = ax.get_legend_handles_labels()
        if handles and labels:
            ax.legend(loc='upper right', fontsize=8, framealpha=0.9)


class BatteryPopup(PlotPopup):
    """
    Specialized popup for battery component.
    """
    
    def __init__(self, digital_twin=None, current_state=None, parent=None):
        super().__init__(
            title="Battery Status",
            digital_twin=digital_twin,
            columns=['SOC', 'SOH', 'Battery_Temp'],
            current_state=current_state,
            parent=parent
        )


class MotorPopup(PlotPopup):
    """
    Specialized popup for motor component.
    """
    
    def __init__(self, digital_twin=None, current_state=None, parent=None):
        super().__init__(
            title="Motor Status",
            digital_twin=digital_twin,
            columns=['Motor_RPM', 'Motor_Torque', 'Motor_Temp'],
            current_state=current_state,
            parent=parent
        )


class WheelPopup(PlotPopup):
    """
    Specialized popup for wheel/tire component.
    """
    
    def __init__(self, digital_twin=None, current_state=None, parent=None):
        super().__init__(
            title="Wheel/Tire Status",
            digital_twin=digital_twin,
            columns=['Tire_Pressure', 'Brake_Pad_Wear'],
            current_state=current_state,
            parent=parent
        )
