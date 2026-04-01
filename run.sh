set -e

BASE=$(pwd)
TESTS=${BASE}/Matrix-tests
LINUX=${BASE}/linux-kernel
NEMU=${BASE}/NEMU-Matrix
TLTEST=${BASE}/tl-test-new-matrix

CFG_INI=${BASE}/configuration.ini
CFG_GEN=${BASE}/scripts/gen_testtop_ini_params.py
CFG_SCALA_OUT=${BASE}/CoupledL2/src/test/scala/TestTopIniParams.scala
CFG_MATRIX_HEADER_OUT=${BASE}/Matrix-tests/isa/generated_matrix_config.h
CFG_TLTEST_INI_OUT=${BASE}/tl-test-new-matrix/configs/user.tltest.ini

THREADS_BUILD=${THREADS_BUILD:-$(($(nproc)/2))}

print_help() {
    echo "Usage: $0 [-mntclrTa]"
    echo "  -m: build matrix workload + linux kernel + opensbi"
    echo "  -n: build NEMU"
    echo "  -t: generate workload trace on NEMU"
    echo "  -T: run -t on remote host via ssh and fetch line_trace.txt"
    echo "  -c: RTL and verilator compilation"
    echo "  -l: tl-test compilation"
    echo "  -r: run trace on TL-Test"
    echo "  -a: analyze latest run (ini/cycles/counters/plot)"
}

M=0
N=0
T=0
RT=0
C=0
L=0
R=0
A=0

REMOTE_HOST=${REMOTE_HOST:-172.19.20.103}
REMOTE_USER=${REMOTE_USER:-}
REMOTE_BASE=${REMOTE_BASE:-${BASE}}

if [ -n "${REMOTE_USER}" ]; then
    SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
else
    SSH_TARGET="${REMOTE_HOST}"
fi

if [ $# -eq 0 ]; then
    print_help
    exit 1
fi

while getopts "mntclrTa" OPT; do
    case $OPT in
        m) M=1;;
        n) N=1;;
        t) T=1;;
        T) RT=1;;
        c) C=1;;
        l) L=1;;
        r) R=1;;
        a) A=1;;
        \?)
            echo "Unknown option: -$OPT"
            print_help
            exit 1
            ;;
    esac
done

if [ $M -eq 1 ] || [ $N -eq 1 ] || [ $L -eq 1 ] || [ $R -eq 1 ] || [ $T -eq 1 ] || [ $C -eq 1 ]; then
    echo "********** generate configuration artifacts **********"
    python3 ${CFG_GEN} --ini ${CFG_INI} --out-scala ${CFG_SCALA_OUT} --out-matrix-header ${CFG_MATRIX_HEADER_OUT} --out-tltest-ini ${CFG_TLTEST_INI_OUT}
fi

if [ $M -eq 1 ]; then
    echo "********** build matrix workload **********"
    cd ${TESTS}
    ./compiler.sh ./isa/xiangshan_mul_full.c
    cd ${BASE}

    # make -C ${LINUX}/linux-6.10.3 clean -j${THREADS_BUILD}
    # make -C ${LINUX}/linux-6.10.3 xiangshan_defconfig -j${THREADS_BUILD}

    echo "********** build linux kernel **********"
    rm ${LINUX}/linux-6.10.3/vmlinux.o
    make -C ${LINUX}/linux-6.10.3 -j${THREADS_BUILD}

    echo "********** build opensbi **********"
    make -C ${LINUX}/opensbi PLATFORM=generic FW_PAYLOAD_PATH=$RISCV_LINUX_HOME/arch/riscv/boot/Image FW_FDT_PATH=$WORKLOAD_BUILD_ENV_HOME/dts/build/xiangshan.dtb FW_PAYLOAD_OFFSET=0x200000 -j${THREADS_BUILD}
fi

if [ $N -eq 1 ]; then
    echo "********** build NEMU **********"
    # make -C ${NEMU} riscv64-matrix-xs_defconfig
    make -C ${NEMU} -j${THREADS_BUILD}
fi

if [ $T -eq 1 ]; then
    echo "********** run workload on NEMU **********"
    ${NEMU}/build/riscv64-nemu-interpreter -b ${LINUX}/opensbi/build/platform/generic/firmware/fw_payload.bin 1> ${NEMU}/stdout.txt 2> ${NEMU}/stderr.txt
    echo "Done"

    cd ${NEMU} && python3 addr.py && cd ${BASE}
    echo "addr.py parse"

    cp ${NEMU}/line_trace.txt ${TLTEST}
fi

if [ $RT -eq 1 ]; then
    echo "********** run workload on remote NEMU (${SSH_TARGET}) **********"
    ssh ${SSH_TARGET} "bash -lc 'set -e; cd \"${REMOTE_BASE}\"; source env.sh; ./run.sh -t'"
fi

if [ $C -eq 1 ]; then
    echo "********** RTL and verilator compilation **********"
    L=1
    cd ${TLTEST}
    make coupledL2-compile -j${THREADS_BUILD}
    make coupledL2-verilog-test-top-l2l3  -j${THREADS_BUILD}
    make coupledL2-verilate -j${THREADS_BUILD}
    cd ..
fi

if [ $L -eq 1 ]; then
    echo "********** tl-test compilation **********"
    cd ${TLTEST}
    make tltest-config-coupledL2-test-l2l3-full -j${THREADS_BUILD}
    make tltest-build-all-coupledL2 -j${THREADS_BUILD}
    cd ..
fi

if [ $R -eq 1 ]; then
    echo "********** run trace on TL-Test **********"
    cd ${TLTEST}
    make run
    PERF_LOG=${TLTEST}/run/tltest_v3lt_perf.log
    if [ -f ${TLTEST}/run/tltest_v3lt.log ]; then
        awk '/^\[PERF \]/{print}' ${TLTEST}/run/tltest_v3lt.log > ${PERF_LOG}
        echo "PERF lines saved to ${PERF_LOG}"
    else
        echo "Warning: ${TLTEST}/run/tltest_v3lt.log not found, skip PERF extraction"
    fi
    cd ..
fi

if [ $A -eq 1 ]; then
    echo "********** analyze latest run **********"
    python3 ${BASE}/scripts/analyze_run.py \
      --ini ${CFG_INI} \
      --log ${TLTEST}/run/tltest_v3lt.log \
      --perf ${TLTEST}/run/tltest_v3lt_perf.log \
      --db ${TLTEST}/run/chiseldb.db
fi

