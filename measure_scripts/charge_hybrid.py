import argparse
import os
import numpy as np
import time
import arg_config as argc
import run_functions as rf

from pygamry.dtaq import get_pstat, DtaqChrono, DtaqPstatic, GamryCOM, HybridSequencer

# Define args
parser = argparse.ArgumentParser(
    description="Charge/discharge at constant current while running hybrid measurements"
)
# Add predefined arguments
argc.add_args_from_dict(parser, argc.common_args)
argc.add_args_from_dict(parser, argc.hybrid_args)

parser.add_argument("--condition_time", type=float, default=0)
parser.add_argument("--condition_t_sample", type=float, default=1e-3)
parser.add_argument("--max_repeats", type=int, default=1)
parser.add_argument("--duration", type=float, default=3600)
parser.add_argument("--stop_v_min", type=float, default=-1)
parser.add_argument("--stop_v_max", type=float, default=1)

parser.add_argument("--voltage_finish", default=False, action="store_true")
parser.add_argument("--finish_v", type=float, default=0.0)
parser.add_argument("--finish_i_thresh", type=float, default=0.005)
parser.add_argument("--finish_i_max", type=float, default=1.0)
parser.add_argument("--finish_t_sample", type=float, default=1)
parser.add_argument("--finish_duration", type=float, default=3600)
parser.add_argument("--finish_rest_time", type=float, default=2)

if __name__ == "__main__":
    # Parse args
    args = parser.parse_args()

    # Get pstat
    pstat = get_pstat()

    # Configure sequencer
    seq = HybridSequencer(mode="galv", update_step_size=True, exp_notes=args.exp_notes)

    # Get DC current sign
    i_sign = np.sign(args.hybrid_i_init)

    # Mark start time
    start_time = time.time()

    # Condition
    if args.condition_time > 0:
        dt_chrono = DtaqChrono(mode="galv")

        dt_chrono.configure_mstep_signal(
            0,
            args.hybrid_i_init,
            1,
            args.condition_time,
            args.condition_t_sample,
            n_steps=1,
        )
        dt_chrono.leave_cell_on = True
        start_with_cell_off = False

        dt_chrono.configure_decimation("write", 20, 10, 2, 1)

        print(
            "Conditioning at {:.3f} A for {:.0f} s...".format(
                args.hybrid_i_init, args.condition_time
            )
        )
        chrono_file = os.path.join(
            args.data_path, f"Conditioning_{args.file_suffix}.DTA"
        )

        if args.kst_path is not None:
            kst_file = os.path.join(args.kst_path, "Kst_IVT.DTA")
        else:
            kst_file = None

        dt_chrono.run(pstat, result_file=chrono_file, kst_file=kst_file, decimate=True)
    else:
        start_with_cell_off = True

    # Run hybrid measurements
    leave_cell_on = True
    for n in range(args.max_repeats):
        print(f"Beginning cycle {n}\n-----------------------------")
        # If repeating measurement, add indicator for cycle number
        if args.max_repeats > 1:
            suffix = args.file_suffix + f"_Cycle{n}"
        else:
            suffix = args.file_suffix

        # After first run, start with cell on
        if n > 0:
            start_with_cell_off = False

        # At last run, turn cell off
        if n == args.max_repeats - 1:
            leave_cell_on = False

        rf.run_hybrid(
            seq,
            pstat,
            args,
            suffix,
            show_plot=False,
            start_with_cell_off=start_with_cell_off,
            leave_cell_on=leave_cell_on,
        )

        stop = False
        # Check voltage limits
        if seq.meas_v_min <= args.stop_v_min:
            print(
                "STOPPING CHARGE/DISCHARGE: measured voltage {:.3f} V is below low threshold ({:.3f} V)".format(
                    seq.meas_v_min, args.stop_v_min
                )
            )
            stop = True

        if seq.meas_v_max >= args.stop_v_max:
            print(
                "STOPPING CHARGE/DISCHARGE: measured voltage {:.3f} V is above high threshold ({:.3f} V)".format(
                    seq.meas_v_max, args.stop_v_max
                )
            )
            stop = True

        # Check for voltage finish
        if args.voltage_finish and seq.meas_v_end * i_sign >= args.finish_v * i_sign:
            print(
                "STOPPING CHARGE/DISCHARGE: "
                "measured voltage {:.3f} V has reached finishing voltage ({:.3f} V)".format(
                    seq.meas_v_end, args.finish_v
                )
            )
            stop = True

        # Check if duration exceeded
        elapsed = time.time() - start_time
        if elapsed >= args.duration:
            print(
                "STOPPING CHARGE/DISCHARGE: "
                "elapsed time {:.0f} s has reached target duration ({:.0f} s)".format(
                    elapsed, args.duration
                )
            )
            stop = True

        if stop:
            # Turn cell off and close pstat
            if pstat.TestIsOpen():
                pstat.SetCell(GamryCOM.CellOff)
                pstat.Close()
            break
        else:
            print(
                "Resting for {:.1f} s between cycles...".format(args.hybrid_rest_time)
            )

    # Perform potentiostatic voltage finish
    if args.voltage_finish:
        print(
            "Resting for {:.1f} s before voltage finish...".format(
                args.finish_rest_time
            )
        )
        time.sleep(args.finish_rest_time)

        dt_pstatic = DtaqPstatic()

        pstatic_file = os.path.join(
            args.data_path, f"PSTATIC-FINISH_{args.file_suffix}.DTA"
        )

        if args.kst_path is not None:
            kst_file = os.path.join(args.kst_path, "Kst_IVT.DTA")
        else:
            kst_file = None

        # Set current cutoff
        if i_sign > 0:
            i_min = abs(args.finish_i_thresh)
            i_max = abs(args.finish_i_max)
        else:
            i_min = abs(args.finish_i_max) * i_sign
            i_max = abs(args.finish_i_thresh) * i_sign

        print(
            "Voltage finish current limits: ({:.4f} A, {:.4f} A)".format(i_min, i_max)
        )

        dt_pstatic.run(
            pstat,
            args.finish_v,
            args.finish_duration,
            args.finish_t_sample,
            i_min=i_min,
            i_max=i_max,
            result_file=pstatic_file,
            kst_file=kst_file,
        )
