#!/usr/bin/env python
#
#  Pocket SDR Python AP - GNSS Signal Acquisition
#
#  Author:
#  T.TAKASU
#
#  History:
#  2021-12-01  1.0  new
#  2021-12-05  1.1  add signals: G1CA, G2CA, B1I, B2I, B1CD, B1CP, B2AD, B2AP,
#                   B2BI, B3I
#  2021-12-15  1.2  add option: -d, -nz, -np
#
import sys, time
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import sdr_func, sdr_code

mpl.rcParams['toolbar'] = 'None';
mpl.rcParams['font.size'] = 9

# show usage -------------------------------------------------------------------
def show_usage():
    print('Usage: pocket_acq.py [-sig sig] [-prn prn[,...]] [-tint tint]')
    print('       [-toff toff] [-f freq] [-fi freq] [-d freq] [-nz] [-np]')
    print('       [-p] [-3d] file')
    exit()

# plot C/N0 --------------------------------------------------------------------
def plot_cn0(ax, cn0, prns, fc):
    thres = 40.0
    x = np.arange(len(cn0))
    y = cn0
    ax.bar(x[y <  thres], y[y <  thres], color='gray', width=0.6)
    ax.bar(x[y >= thres], y[y >= thres], color=fc    , width=0.6)
    ax.grid(True, lw=0.4)
    ax.set_xlim([x[0] - 0.5, x[-1] + 0.5])
    plt.xticks(x, ['%d' % (prn) for prn in prns])
    ax.set_ylim([30, 50])
    ax.set_xlabel('PRN Number')
    ax.set_ylabel('C/N0 (dB-Hz)')

# plot correlation 3D ----------------------------------------------------------
def plot_corr_3d(ax, P, dops, coffs, ix, fc):
    x, y = np.meshgrid(coffs * 1e3, dops)
    z = P / np.mean(P) * 0.015
    #ax.plot_wireframe(x, y, z, rstride=1, cstride=0, color=fc, lw=0.3, alpha=0.8)
    ax.plot_surface(x, y, z, rstride=1, cstride=1, cmap='Greys', vmax=2, lw=0.1, edgecolor='k')
    #ax.plot_surface(x, y, z, rstride=1, cstride=1, cmap='Blues', vmax=2, lw=0.1, edgecolor='b')
    ax.set_xlim([x[0][0], x[0][-1]])
    ax.set_ylim([y[0][0], y[-1][0]])
    ax.set_zlim([0, 1])
    ax.set_xlabel('Code Offset (ms)')
    ax.set_ylabel('Doppler Frequency (Hz)')
    ax.set_zlabel('Correlation Power')
    ax.set_box_aspect((1, 1, 0.6))
    ax.xaxis.set_pane_color((1, 1, 1, 0))
    ax.yaxis.set_pane_color((1, 1, 1, 0))
    ax.xaxis._axinfo["grid"]['color'] =  (1, 1, 1, 0)
    ax.yaxis._axinfo["grid"]['color'] =  (1, 1, 1, 0)
    ax.zaxis._axinfo["grid"]['color'] =  (1, 1, 1, 0)
    ax.view_init(20, -50)

# plot correlation power -------------------------------------------------------
def plot_corr_pow(ax, P, f, fc):
    x = np.arange(len(P)) / f
    y = P
    ax.plot(x, y, '-', color='grey', lw=0.5)
    ax.plot(x, y, '.', color=fc, ms=3)
    ax.grid(True, lw=0.4)
    ax.set_xlim([x[0], x[-1]])
    ax.set_ylim([0, 1])
    ax.set_ylabel('Correlation Power')

# plot correlation peak ---------------------------------------------------------
def plot_corr_peak(ax, P, ix, f, fc):
    x = (np.arange(len(P)) - ix) / f
    y = P
    ax.plot(x, y, '-', color='gray', lw=0.5)
    ax.plot(x, y, '.', color=fc, ms=3)
    ax.grid(True, lw=0.4)
    ax.set_xlim([-4.5, 4.5])
    ax.set_ylim([0, 1])
    ax.set_ylabel('Correlation Power')

# add text annotation in plot --------------------------------------------------
def add_text(ax, x, y, text, color='k'):
    ax.text(x, y, text, ha='right', va='top', c=color, transform=ax.transAxes)

#-------------------------------------------------------------------------------
#
#   Synopsis
# 
#     pocket_aqc.py [-sig sig] [-prn prn] [-tint tint] [-toff toff] [-f freq]
#         [-fi freq] [-d freq] [-nz] [-np] [-p] [-3d] file
# 
#   Description
# 
#     Search GNSS signals in digital IF data and plot signal search results.
#     If single PRN number by -prn option, it plots correlation power and
#     correlation shape of the specified GNSS signal. If multiple PRN numbers
#     specified by -prn option, it plots C/N0 for each PRN.
# 
#   Options ([]: default)
#  
#     -sig sig
#         GNSS signal type (L1CA, L1CB, L1CP, L1CD, L2CM, L5I, L5Q, L6D, L6E,
#         G1CA, G2CA, E1B, E1C, E5AI, E5AQ, E5BI, E5BQ, E6B, E6C, B1I, B1CD,
#         B1CP, B2I, B2AD, B2AP, B2BI, B3I). [L1CA]
# 
#     -prn prn[,...]
#         PRN numbers of the GNSS signal separated by ','. A PRN number can be a
#         PRN number range like 1-32 with start and end PRN numbers. For GLONASS
#         FDMA signals (G1CA, G2CA), the PRN number is treated as FCN (frequency
#         channel number). [1]
# 
#     -tint tint
#         Integration time in ms to search GNSS signals. [code cycle]
# 
#     -toff toff
#         Time offset from the start of digital IF data in ms. [0.0]
# 
#     -f freq
#         Sampling frequency of digital IF data in MHz. [12.0]
#
#     -fi freq
#         IF frequency of digital IF data in MHz. The IF frequency equals 0, the
#         IF data is treated as IQ-sampling (zero-IF). [0.0]
#
#     -d freq
#         Max Doppler frequency to search the signal in Hz. [5000.0]
#
#     -nz
#         Disalbe zero-padding for circular colleration to search the signal.
#         [enabled]
#
#     -np
#         Disable plot even with single PRN number. [enabled]
#
#     -p
#         Plot correlation powers with correlation peak graph.
#
#     -3d
#         Plot correlation powers in a 3D-plot.
#
#     file
#         File path of the input digital IF data. The format should be a series of
#         int8_t (signed byte) for real-sampling (I-sampling) or interleaved int8_t
#         for complex-sampling (IQ-sampling). PocketSDR and AP pocket_dump can be
#         used to capture such digital IF data.
#
if __name__ == '__main__':
    window = 'PocketSDR - GNSS SIGNAL ACQUISITION'
    size = (9, 6)
    sig, prns = 'L1CA', [1]
    fs, fi, T, toff = 12e6, 0.0, 4e-3, 0.0
    max_dop = 5000.0
    opt = [False, False, True, False]
    fc, bc = 'darkblue', 'w'
    rect0 = [0.08, 0.09, 0.84, 0.85]
    rect1 = [0.08, 0.53, 0.84, 0.41]
    rect2 = [0.08, 0.07, 0.84, 0.41]
    rect3 = [0, -0.05, 1, 1.25]
    file = ''
    label = 'PRN'
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-sig':
            i += 1
            sig = sys.argv[i]
        elif sys.argv[i] == '-prn':
            i += 1
            prns = sdr_func.parse_nums(sys.argv[i])
        elif sys.argv[i] == '-tint':
            i += 1
            T = float(sys.argv[i]) * 1e-3
        elif sys.argv[i] == '-toff':
            i += 1
            toff = float(sys.argv[i]) * 1e-3
        elif sys.argv[i] == '-f':
            i += 1
            fs = float(sys.argv[i]) * 1e6
        elif sys.argv[i] == '-fi':
            i += 1
            fi = float(sys.argv[i]) * 1e6
        elif sys.argv[i] == '-d':
            i += 1
            max_dop = float(sys.argv[i])
        elif sys.argv[i] == '-p':
            opt[0] = True
        elif sys.argv[i] == '-3d':
            opt[1] = True
        elif sys.argv[i] == '-nz':
            opt[2] = False
        elif sys.argv[i] == '-np':
            opt[3] = True
        elif sys.argv[i][0] == '-':
            show_usage()
        else:
            file = sys.argv[i];
        i += 1
    
    if file == '':
        print('Specify input file.')
        exit()
    
    Tcode = sdr_code.code_cyc(sig) # code cycle (s)
    if Tcode <= 0:
        print('Invalid signal %s.' % (sig))
        exit()

    # integration time (s)
    if T < Tcode:
        T = Tcode
    
    if sig == 'G1CA' or sig == 'G2CA':
        label = 'FCN'
    
    try:
        # read IF data
        data = sdr_func.read_data(file, fs, 1 if fi > 0 else 2, T + Tcode, toff)
        
        if not opt[3]:
            fig = plt.figure(window, figsize=size)
            ax0 = fig.add_axes(rect0)
            ax0.axis('off')
        t = time.time()
        
        if len(prns) > 1:
            cn0 = np.zeros(len(prns))
            for i in range(len(prns)):
                P, dops, coffs, ix, cn0[i] = sdr_func.search_sig(sig,
                    prns[i], data, fs, fi, max_dop=max_dop, zero_pad=opt[2])
                
                print('SIG= %-4s, %s= %3d, COFF= %8.5f ms, DOP= %5.0f Hz, C/N0= %4.1f dB-Hz' % \
                    (sig, label, prns[i], coffs[ix[1]] * 1e3, dops[ix[0]], cn0[i]))
            
            t = time.time() - t
            ax1 = fig.add_axes(rect0, facecolor=bc)
            plot_cn0(ax1, cn0, prns, fc)
            ax0.set_title('SIG = %s, FILE = %s' % (sig, file), fontsize=10)
        else:
            P, dops, coffs, ix, cn0 = \
                sdr_func.search_sig(sig, prns[0], data, fs, fi, max_dop=max_dop,
                    zero_pad=opt[2])
            t = time.time() - t
            text = 'COFF=%.5fms, DOP=%.0fHz, C/N0=%.1fdB-Hz' % \
                   (coffs[ix[1]] * 1e3, dops[ix[0]], cn0)
            if opt[3]: # text
                print('SIG= %-4s, %s= %3d, COFF= %8.5f ms, DOP= %5.0f Hz, C/N0= %4.1f dB-Hz' % \
                    (sig, label, prns[0], coffs[ix[1]] * 1e3, dops[ix[0]], cn0))
                exit()
            elif opt[1]: # plot 3D
                ax1 = fig.add_axes(rect3, projection='3d', facecolor='None')
                plot_corr_3d(ax1, P, dops, coffs, ix, fc)
                add_text(ax0, 0.98, 0.96, text, color=fc)
            elif opt[0]: # plot power + peak
                ax1 = fig.add_axes(rect1, facecolor=bc)
                plot_corr_pow(ax1, P[ix[0]], fs / 1e3, fc)
                add_text(ax1, 1.04, -0.04, '(ms)')
                add_text(ax1, 0.98, 0.94, text, color=fc)
                ax2 = fig.add_axes(rect2, facecolor=bc)
                f = fs * Tcode / sdr_code.code_len(sig)
                plot_corr_peak(ax2, P[ix[0]], ix[1], f, fc)
                add_text(ax2, 1.04, -0.04, '(chip)')
            else: # plot power
                ax1 = fig.add_axes(rect0, facecolor=bc)
                plot_corr_pow(ax1, P[ix[0]], fs / 1e3, fc)
                ax1.set_xlabel('Code Offset (ms)')
                add_text(ax1, 0.98, 0.97, text)
            
            ax0.set_title('SIG = %s, %s = %d, FILE = %s' % \
                (sig, label, prns[0], file), fontsize=10)
        
        print('TIME = %.1f ms' % (t * 1e3))
        plt.show()
    
    except KeyboardInterrupt:
        exit()
