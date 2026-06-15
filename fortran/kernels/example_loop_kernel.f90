module example_loop_kernel
  use, intrinsic :: iso_c_binding
  implicit none
contains

  function i3_kernel(mphi, mphip, mpsi) result(value) bind(C, name="bsm_i3_kernel")
    real(c_double), value :: mphi
    real(c_double), value :: mphip
    real(c_double), value :: mpsi
    real(c_double) :: value
    real(c_double), parameter :: pi = 3.141592653589793d0
    real(c_double) :: a
    real(c_double) :: b

    a = (mphi*mphi * log((mpsi*mpsi)/(mphi*mphi))) / &
        ((mphi*mphi - mphip*mphip) * (mphi*mphi - mpsi*mpsi))
    b = (mphip*mphip * log((mpsi*mpsi)/(mphip*mphip))) / &
        ((mphip*mphip - mphi*mphi) * (mphip*mphip - mpsi*mpsi))

    value = -(a + b) / ((4.0d0*pi) * (4.0d0*pi))
  end function i3_kernel

end module example_loop_kernel

