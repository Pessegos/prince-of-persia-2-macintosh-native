"""Writing opaque pixels into part of a Tk photo through Tk's own function.

Tk's photo commands take the pixels of a part as image data, which Tk 8.6 reads
at about 26 ns a pixel (1.8 ms for an option of a menu at 3440x1440), or from
another photo, which makes Tk look over the alpha of the whole photo it writes
into (about 1.3 ms at that size, however small the part). Both end in
Tk_PhotoPutBlock, which Pillow's ImageTk also calls for a whole photo: called
directly, it takes the pixels where they are, about 5 ns a pixel, most of it
Tk preparing them for the display. When Tk's function cannot be reached, or the
Tk in use is not the one whose structures are declared here, put_pixels says so
and the caller writes the part as before.
"""

import ctypes
import sys
from _tkinter import TclError

import numpy

TK_PHOTO_COMPOSITE_SET = 1


class PhotoBlock(ctypes.Structure):
    """Tk_PhotoImageBlock, as tk.h declares it for Tk 8.6."""
    _fields_ = [('pixelPtr', ctypes.c_void_p), ('width', ctypes.c_int), ('height', ctypes.c_int),
                ('pitch', ctypes.c_int), ('pixelSize', ctypes.c_int), ('offset', ctypes.c_int * 4)]


_writers = {}   # Tcl interpreter's address -> write(name, pixels, x, y), or None


def _tk_library(interp):
    """Tk's library as this process loaded it for ``interp``, or None."""
    if str(interp.getvar('tk_version')) != '8.6':
        return None
    if sys.platform == 'win32':
        kernel32 = ctypes.WinDLL('kernel32')
        kernel32.GetModuleHandleW.argtypes = (ctypes.c_wchar_p,)
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        for name in ('tk86t.dll', 'tk86.dll'):
            handle = kernel32.GetModuleHandleW(name)   # only one already loaded
            if handle:
                return ctypes.CDLL(name, handle=handle)
        return None
    import _tkinter
    return ctypes.CDLL(_tkinter.__file__)   # its symbols include those of the Tk it links


def _writer(interp):
    library = _tk_library(interp)
    if library is None:
        return None
    find, put = library.Tk_FindPhoto, library.Tk_PhotoPutBlock
    find.argtypes, find.restype = (ctypes.c_void_p, ctypes.c_char_p), ctypes.c_void_p
    put.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(PhotoBlock),
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
    put.restype = ctypes.c_int
    address = ctypes.c_void_p(interp.interpaddr())

    def write(name, pixels, x, y):
        photo = find(address, name.encode())
        if not photo:
            raise ValueError(f'no photo named {name}')
        height, width, size = pixels.shape
        # An alpha offset of 0 marks the pixels opaque: Tk then neither keeps their
        # alpha nor looks over the whole photo's.
        block = PhotoBlock(pixels.ctypes.data, width, height, pixels.strides[0], size, (0, 1, 2, 0))
        if put(address, photo, ctypes.byref(block), x, y, width, height, TK_PHOTO_COMPOSITE_SET) != 0:
            raise MemoryError(f'Tk could not make {name} {x + width}x{y + height}')

    # Write two pixels into a photo of its own and read them back before trusting it.
    probe = interp.call('image', 'create', 'photo', '-width', 3, '-height', 1)
    try:
        write(str(probe), numpy.array([[[10, 20, 30, 0], [40, 50, 60, 128]]], numpy.uint8), 1, 0)
        shown = [tuple(int(value) for value in interp.splitlist(interp.call(probe, 'get', column, 0)))
                 for column in (1, 2)]
        opaque = [not interp.getboolean(interp.call(probe, 'transparency', 'get', column, 0)) for column in (1, 2)]
        if shown != [(10, 20, 30), (40, 50, 60)] or not all(opaque):
            return None
    finally:
        interp.call('image', 'delete', probe)
    return write


def put_pixels(photo, pixels, x, y):
    """Write ``pixels`` into the Tk ``photo`` with their top left corner at (x, y), as
    opaque: an array of rows of RGB or RGBA bytes (alpha ignored) or a picture in either
    mode. True when written; False, and the photo unchanged, when Tk's own function is
    not available."""
    interp = photo.tk
    key = interp.interpaddr()
    if key not in _writers:
        try:
            _writers[key] = _writer(interp)
        except (OSError, AttributeError, TypeError, ValueError, ctypes.ArgumentError, TclError):
            _writers[key] = None
    write = _writers[key]
    if write is None:
        return False
    if not isinstance(pixels, numpy.ndarray):
        if pixels.mode not in ('RGB', 'RGBA'):
            pixels = pixels.convert('RGB')
        pixels = numpy.asarray(pixels)
    if pixels.dtype != numpy.uint8 or pixels.ndim != 3 or pixels.shape[2] not in (3, 4):
        raise ValueError(f'not rows of RGB or RGBA bytes: {pixels.dtype} {pixels.shape}')
    if pixels.strides[1:] != (pixels.shape[2], 1) or pixels.strides[0] < pixels.shape[1] * pixels.shape[2]:
        pixels = numpy.ascontiguousarray(pixels)   # Tk reads each row's pixels side by side
    if pixels.shape[0] and pixels.shape[1]:
        write(str(photo), pixels, int(x), int(y))
    return True
