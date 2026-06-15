# Flavor Toy Example

This is a minimal validation example for the generic flavor-sector machinery.

It demonstrates:

- Takagi diagonalization of a complex symmetric Majorana neutrino mass matrix
- SVD/biunitary diagonalization of charged-lepton, up-quark, and down-quark mass matrices
- PMNS construction as `U_l_L^\dagger U_nu`
- CKM construction as `U_u_L^\dagger U_d_L`
- reusable CKM scalar observables imported from `core/quark/ckm_observables.yaml`
- broad toy CKM Gaussian likelihoods for framework validation

The numbers are pedagogical and are not intended as a realistic flavor fit.
The toy CKM likelihood values are not production global-fit inputs.
