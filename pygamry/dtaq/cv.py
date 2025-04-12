import comtypes.client as client

from ..utils import rel_round
from .config import GamryCOM
from .eventsink import GamryDtaqEventSink


class DtaqCV(GamryDtaqEventSink):
    """
    Class for Cyclic Voltammetry
    """

    def __init__(self, **init_kw):
        # Define axes for real-time plotting
        axes_def = [
            {
                "title": "Cyclic Voltammogram",
                "type": "y(x)",
                "x_column": "Vf",
                "y_column": "Im",
                "x_label": "$E$ (V)",
                "y_label": "$i$ (A)",
            },
            {
                "title": "Current vs Time",
                "type": "y(t)",
                "y_column": "Im",
                "y_label": "$i$ (A)",
            },
            {
                "title": "Voltage vs Time",
                "type": "y(t)",
                "y_column": "Vf",
                "y_label": "$E$ (V)",
            },
        ]

        # Initialize subclass attributes
        self.v_oc = None
        self.i_min = None
        self.i_max = None
        self.cycles = None

        super().__init__(
            "GamryDtaqCV",
            "CYCLIC_VOLTAMMETRY",
            axes_def,
            test_id="Cyclic Voltammetry",
            **init_kw,
        )

    # ---------------------------------
    # Initialization and configuration
    # ---------------------------------
    def initialize_pstat(self):
        self.pstat.SetCtrlMode(GamryCOM.PstatMode)
        self.pstat.SetIEStability(GamryCOM.StabilityNorm)
        self.pstat.SetIERangeMode(True)  # Enable auto-ranging

        # Measure OCV with cell off if needed
        if self.start_with_cell_off:
            self.v_oc = self.pstat.MeasureV()
        else:
            self.v_oc = 0

        # Initialize dtaq to pstat
        self.dtaq.Init(self.pstat)

        # Set signal
        self.pstat.SetSignal(self.signal)

        # Set current limits if specified
        if self.i_min is not None:
            self.dtaq.SetThreshIMin(True, self.i_min)
            self.dtaq.SetStopIMin(True, self.i_min)
        if self.i_max is not None:
            self.dtaq.SetThreshIMax(True, self.i_max)
            self.dtaq.SetStopIMax(True, self.i_max)

        # Per Dan Cook's recommendation: Disable Ich ranging, set IchRange to 3, disable Ich and Vch offsets
        self.pstat.SetIchRangeMode(False)
        self.pstat.SetIchRange(3.0)
        self.pstat.SetIchOffsetEnable(False)
        self.pstat.SetVchOffsetEnable(False)

        print("IchRange:", self.pstat.IchRange())

        # Turn cell on
        self.pstat.SetCell(GamryCOM.CellOn)

    def set_signal(
        self, v_init, v_vertex1, v_vertex2, v_final, scan_rate, t_sample, cycles=1
    ):
        """
        Configure cyclic voltammetry signal

        Parameters:
        -----------
        v_init : float
            Initial voltage (V)
        v_vertex1 : float
            First vertex voltage (V)
        v_vertex2 : float
            Second vertex voltage (V)
        v_final : float
            Final voltage (V)
        scan_rate : float
            Scan rate (V/s)
        t_sample : float
            Sample period (s)
        cycles : int, optional
            Number of cycles, default is 1
        """
        self.signal = client.CreateObject("GamryCOM.GamrySignalCyclic")

        # Initialize the cyclic voltammetry signal
        self.signal.Init(
            self.pstat,
            float(v_init),  # Initial voltage
            float(v_vertex1),  # First vertex
            float(v_vertex2),  # Second vertex
            float(v_final),  # Final voltage
            float(scan_rate),  # Scan rate (V/s)
            float(t_sample),  # Sample period (s)
            int(cycles),
        )  # Number of cycles

        # Store signal parameters for reference
        self.signal_params = {
            "v_init": v_init,
            "v_vertex1": v_vertex1,
            "v_vertex2": v_vertex2,
            "v_final": v_final,
            "scan_rate": scan_rate,
            "t_sample": t_sample,
            "cycles": cycles,
        }

        # Store cycles for later reference
        self.cycles = cycles

        # Calculate expected duration
        # Total scan distance calculation
        first_segment = abs(v_vertex1 - v_init)
        cycle_distance = abs(v_vertex1 - v_vertex2) * 2
        final_segment = abs(v_final - v_vertex2)

        # If final voltage equals v_vertex1, we need to adjust
        if abs(v_final - v_vertex1) < 1e-6:
            final_segment = abs(v_final - v_vertex2)

        total_distance = first_segment + (cycle_distance * cycles) + final_segment

        # Duration calculation
        self.expected_duration = total_distance / scan_rate

    # ---------------------------------
    # Run
    # ---------------------------------
    def run(
        self,
        pstat,
        v_init,
        v_vertex1,
        v_vertex2,
        v_final,
        scan_rate,
        t_sample,
        cycles=1,
        timeout=None,
        i_min=None,
        i_max=None,
        result_file=None,
        kst_file=None,
        append_to_file=False,
        show_plot=False,
        plot_interval=None,
    ):
        """
        Run cyclic voltammetry measurement

        Parameters:
        -----------
        pstat : Potentiostat object
            Gamry potentiostat instance
        v_init : float
            Initial voltage (V)
        v_vertex1 : float
            First vertex voltage (V)
        v_vertex2 : float
            Second vertex voltage (V)
        v_final : float
            Final voltage (V)
        scan_rate : float
            Scan rate (V/s)
        t_sample : float
            Sample period (s)
        cycles : int, optional
            Number of cycles, default is 1
        timeout : float, optional
            Maximum measurement time (s)
        i_min : float, optional
            Minimum current threshold (A)
        i_max : float, optional
            Maximum current threshold (A)
        result_file : str, optional
            Path to save result data
        kst_file : str, optional
            Path to save data for Kst plotting
        append_to_file : bool, optional
            Whether to append data to existing file
        show_plot : bool, optional
            Whether to show real-time plot
        plot_interval : float, optional
            Interval for plot updates (s)
        """
        self.pstat = pstat
        self.set_signal(
            v_init, v_vertex1, v_vertex2, v_final, scan_rate, t_sample, cycles
        )

        self.i_min = i_min
        self.i_max = i_max

        if timeout is None:
            timeout = self.expected_duration * 1.5

        if plot_interval is None:
            plot_interval = t_sample * 0.9

        super().run_main(
            pstat,
            result_file,
            kst_file,
            append_to_file,
            timeout=timeout,
            show_plot=show_plot,
            plot_interval=plot_interval,
        )

    # --------------------
    # Header
    # --------------------
    def get_dtaq_header(self):
        text = (
            "ELECTRICALSETTINGS\tGROUP\n"
            + "VINIT\tQUANT\t{:.6e}\tInitial Voltage (V)\n".format(
                self.signal_params["v_init"]
            )
            + "VVERTEX1\tQUANT\t{:.6e}\tVertex 1 Voltage (V)\n".format(
                self.signal_params["v_vertex1"]
            )
            + "VVERTEX2\tQUANT\t{:.6e}\tVertex 2 Voltage (V)\n".format(
                self.signal_params["v_vertex2"]
            )
            + "VFINAL\tQUANT\t{:.6e}\tFinal Voltage (V)\n".format(
                self.signal_params["v_final"]
            )
            + "SCANRATE\tQUANT\t{:.6e}\tScan Rate (V/s)\n".format(
                self.signal_params["scan_rate"]
            )
            + "SAMPLETIME\tQUANT\t{:.6e}\tSample Period (s)\n".format(
                self.signal_params["t_sample"]
            )
            + "CYCLES\tQUANT\t{}\tNumber of Cycles\n".format(
                self.signal_params["cycles"]
            )
            + f"EOC\tQUANT\t{rel_round(self.v_oc, self.write_precision)}\tOpen Circuit(V)\n"
        )
        return text
