// Running DFT: acc[f, k] += field[index[k]] * phasor[f]
//
// Reference: NumpyBackend.accumulate_dft. Complex arrays are interleaved (re, im)
// pairs of REAL; a real field times a complex phasor is (v * re, v * im), which is
// what NumPy's complex product gives when the imaginary part of the field is 0.
// One thread per (node k, frequency f): blockIdx.y = f.

extern "C" __global__ void accumulate_dft(
    REAL* __restrict__ acc,                // (n_f, n_nodes) complex
    const REAL* __restrict__ field,        // component array, flat
    const long long* __restrict__ index,   // (n_nodes,)
    const REAL* __restrict__ phasor,       // (n_f,) complex: exp(i w t) dt
    const int n_f, const int n_nodes)
{
    const int k = blockIdx.x * blockDim.x + threadIdx.x;
    const int f = blockIdx.y;
    if (k >= n_nodes || f >= n_f) return;

    const REAL v = field[index[k]];
    const long long a = 2 * ((long long)f * n_nodes + k);
    acc[a] = acc[a] + v * phasor[2 * f];
    acc[a + 1] = acc[a + 1] + v * phasor[2 * f + 1];
}
