"""Kill only our worker process tree if the desktop app exits unexpectedly."""
import ctypes as c
from ctypes import wintypes as w

class BASIC(c.Structure):
    _fields_=[('PerProcessUserTimeLimit',c.c_int64),('PerJobUserTimeLimit',c.c_int64),('LimitFlags',w.DWORD),
              ('MinimumWorkingSetSize',c.c_size_t),('MaximumWorkingSetSize',c.c_size_t),('ActiveProcessLimit',w.DWORD),
              ('Affinity',c.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class IO(c.Structure):
    _fields_=[(n,c.c_uint64) for n in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
class EXT(c.Structure):
    _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO),('ProcessMemoryLimit',c.c_size_t),
              ('JobMemoryLimit',c.c_size_t),('PeakProcessMemoryUsed',c.c_size_t),('PeakJobMemoryUsed',c.c_size_t)]

class Job:
    def __init__(self):
        self.k=c.WinDLL('kernel32',use_last_error=True)
        self.k.CreateJobObjectW.restype=w.HANDLE
        self.k.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR]
        self.k.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]
        self.k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
        self.k.CloseHandle.argtypes=[w.HANDLE]
        self.handle=self.k.CreateJobObjectW(None,None)
        if not self.handle:raise c.WinError(c.get_last_error())
        limits=EXT();limits.BasicLimitInformation.LimitFlags=0x2000
        if not self.k.SetInformationJobObject(self.handle,9,c.byref(limits),c.sizeof(limits)):
            raise c.WinError(c.get_last_error())
    def assign(self,process):
        if not self.k.AssignProcessToJobObject(self.handle,int(process._handle)):
            raise c.WinError(c.get_last_error())
    def close(self):
        if self.handle:self.k.CloseHandle(self.handle);self.handle=None
