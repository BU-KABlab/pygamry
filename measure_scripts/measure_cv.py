import argparse
import time

import arg_config as argc
import run_functions as rf

from pygamry.dtaq import DtaqCV, get_pstat

# Define args
parser = argparse.ArgumentParser(description="Run Cyclic Voltammetry")
# Add predefined arguments
argc.add_args_from_dict(parser, argc.common_args)

# Add CV-specific arguments
cv_args = {
    "--cv_v_init": dict(type=float, default=0.0, help="Initial voltage (V)"),
    "--cv_v_vertex1": dict(type=float, default=0.5, help="First vertex voltage (V)"),
    "--cv_v_vertex2": dict(type=float, default=-0.5, help="Second vertex voltage (V)"),
    "--cv_v_final": dict(type=float, default=0.0, help="Final voltage (V)"),
    "--cv_scan_rate": dict(type=float, default=0.05, help="Scan rate (V/s)"),
    "--cv_t_sample": dict(type=float, default=0.01, help="Sample period (s)"),
    "--cv_cycles": dict(type=int, default=3, help="Number of cycles"),
    "--cv_i_min": dict(type=float, default=None, help="Minimum current threshold (A)"),
    "--cv_i_max": dict(type=float, default=None, help="Maximum current threshold (A)"),
    "--cv_vs_ref": dict(
        action="store_true", help="Use potentials vs reference electrode (not OCV)"
    ),
}
argc.add_args_from_dict(parser, cv_args)

if __name__ == "__main__":
    # Parse args
    args = parser.parse_args()

    # Get pstat
    pstat = get_pstat()

    # Configure CV
    # Write to file after completion
    cv = DtaqCV(write_mode="once", write_precision=6, exp_notes=args.exp_notes)

    for n in range(args.num_loops):
        print(f"Beginning cycle {n}\n-----------------------------")

        # If repeating measurement, add indicator for cycle number
        if args.num_loops > 1:
            suffix = args.file_suffix + f"_#{n}"
        else:
            suffix = args.file_suffix

        # Get OCV if needed to use relative potentials
        if not args.cv_vs_ref:
            V_oc = rf.test_ocv(pstat)
            print("OCV: {:.3f} V".format(V_oc))

            # Apply OCV offset to potentials
            v_init = args.cv_v_init + V_oc
            v_vertex1 = args.cv_v_vertex1 + V_oc
            v_vertex2 = args.cv_v_vertex2 + V_oc
            v_final = args.cv_v_final + V_oc
        else:
            # Use potentials directly vs reference
            v_init = args.cv_v_init
            v_vertex1 = args.cv_v_vertex1
            v_vertex2 = args.cv_v_vertex2
            v_final = args.cv_v_final

        # Run Cyclic Voltammetry
        print("Running Cyclic Voltammetry")
        print(
            f"Potential window: {v_init:.3f}V → {v_vertex1:.3f}V → {v_vertex2:.3f}V → {v_final:.3f}V"
        )
        print(f"Scan rate: {args.cv_scan_rate:.3f} V/s, {args.cv_cycles} cycles")

        cv_file = f"CV_{suffix}.DTA"
        result_file = f"{args.data_path}/{cv_file}"

        if args.kst_path is not None:
            kst_file = f"{args.kst_path}/Kst_CV.DTA"
        else:
            kst_file = None

        cv.run(
            pstat,
            v_init,
            v_vertex1,
            v_vertex2,
            v_final,
            args.cv_scan_rate,
            args.cv_t_sample,
            args.cv_cycles,
            i_min=args.cv_i_min,
            i_max=args.cv_i_max,
            result_file=result_file,
            kst_file=kst_file,
            show_plot=args.show_plot,
        )

        print("CV done\n")
        time.sleep(1)
