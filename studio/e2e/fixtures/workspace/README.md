Fixture workspace for studio/e2e (Playwright). Ten scripts are listed; the rest are skipped on purpose.

U0 stand-ins (not runnable etalon scripts): bend_euler, broken_status, dc_gap200, mmi_1x2_sweep,
rings/ring_r10_g180, rings/ring_r10_g200, straight_wg.

U1 (real M0 scripts):
- phc_waveguide.py: a copy of the template, with a real CPU run recorded in .etalon/phc_waveguide.py/
  by ../record.py (plane monitor "field" with Ex, Ey, Hz; point monitors "in" and "out" with Hz;
  1.50, 1.55, 1.60 um). Rerun record.py only when the solver's output or Studio's run format changes.
- misplaced_strip.py: the strip template with the strip at y = 0.6 um instead of 0; the Setup slice
  shows SiO2 (eps 2.085) at (0, 0) and silicon (eps 12.08) on the Ex nodes y = 0.36 ... 0.84 um.
- broken_script.py: raises KeyError 'rnig' at line 12 after printing "building the coupler".
