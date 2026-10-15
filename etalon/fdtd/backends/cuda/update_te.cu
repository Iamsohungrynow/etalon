// 2D TE Yee updates with fused CPML.
//
// The reference implementation, with the equations, is
// etalon/fdtd/backends/numpy_backend.py; every expression below performs the same
// IEEE operations in the same order, and the host compiles this file with
// --fmad=false so that no multiply-add is fused. REAL is #defined by the host as
// float or double.
//
// Arrays are C-ordered (x, y) with y fastest; one thread per node, threadIdx.x
// along y for coalesced access:
//   hz (nx, ny)   ex (nx, ny + 1)   ey (nx + 1, ny)
// CPML profiles are 1D per axis: *_e at integer nodes (n + 1), *_h at half nodes (n).

extern "C" __global__ void update_h_te(
    REAL* __restrict__ hz,
    const REAL* __restrict__ ex,
    const REAL* __restrict__ ey,
    REAL* __restrict__ psi_hz_x,
    REAL* __restrict__ psi_hz_y,
    const REAL* __restrict__ bx_h, const REAL* __restrict__ cx_h, const REAL* __restrict__ ikx_h,
    const REAL* __restrict__ by_h, const REAL* __restrict__ cy_h, const REAL* __restrict__ iky_h,
    const REAL db, const REAL inv_dx, const REAL inv_dy,
    const int nx, const int ny)
{
    const int j = blockIdx.x * blockDim.x + threadIdx.x;
    const int i = blockIdx.y * blockDim.y + threadIdx.y;
    if (i >= nx || j >= ny) return;

    const long long k = (long long)i * ny + j;                 // Hz(i, j) and Ey(i, j)
    const long long k_ex = (long long)i * (ny + 1) + j;        // Ex(i, j)

    const REAL dex_dy = (ex[k_ex + 1] - ex[k_ex]) * inv_dy;
    const REAL dey_dx = (ey[k + ny] - ey[k]) * inv_dx;
    const REAL py = by_h[j] * psi_hz_y[k] + cy_h[j] * dex_dy;
    const REAL px = bx_h[i] * psi_hz_x[k] + cx_h[i] * dey_dx;
    psi_hz_y[k] = py;
    psi_hz_x[k] = px;
    hz[k] = hz[k] + db * ((dex_dy * iky_h[j] + py) - (dey_dx * ikx_h[i] + px));
}

extern "C" __global__ void update_e_te(
    REAL* __restrict__ ex,
    REAL* __restrict__ ey,
    const REAL* __restrict__ hz,
    REAL* __restrict__ psi_ex_y,
    REAL* __restrict__ psi_ey_x,
    const REAL* __restrict__ cb_ex,
    const REAL* __restrict__ cb_ey,
    const REAL* __restrict__ bx_e, const REAL* __restrict__ cx_e, const REAL* __restrict__ ikx_e,
    const REAL* __restrict__ by_e, const REAL* __restrict__ cy_e, const REAL* __restrict__ iky_e,
    const REAL inv_dx, const REAL inv_dy,
    const int nx, const int ny)
{
    const int j = blockIdx.x * blockDim.x + threadIdx.x;  // launched over (nx + 1) x (ny + 1)
    const int i = blockIdx.y * blockDim.y + threadIdx.y;

    // Ex(i, j), i in [0, nx), j in [1, ny - 1]; j = 0 and j = ny stay zero (PEC)
    if (i < nx && j >= 1 && j <= ny - 1) {
        const long long k = (long long)i * (ny + 1) + j;
        const long long k_hz = (long long)i * ny + j;
        const REAL dhz_dy = (hz[k_hz] - hz[k_hz - 1]) * inv_dy;
        const REAL p = by_e[j] * psi_ex_y[k] + cy_e[j] * dhz_dy;
        psi_ex_y[k] = p;
        ex[k] = ex[k] + cb_ex[k] * (dhz_dy * iky_e[j] + p);
    }

    // Ey(i, j), i in [1, nx - 1], j in [0, ny); i = 0 and i = nx stay zero (PEC)
    if (i >= 1 && i <= nx - 1 && j < ny) {
        const long long k = (long long)i * ny + j;  // same index into hz (nx, ny)
        const REAL dhz_dx = (hz[k] - hz[k - ny]) * inv_dx;
        const REAL p = bx_e[i] * psi_ey_x[k] + cx_e[i] * dhz_dx;
        psi_ey_x[k] = p;
        ey[k] = ey[k] - cb_ey[k] * (dhz_dx * ikx_e[i] + p);
    }
}
