#ifndef _HUGE_IC_PLATFORM_H_
#define _HUGE_IC_PLATFORM_H_

#define PRO_TYPE_LMAC 1
#define PRO_TYPE_UMAC 2
#define PRO_TYPE_WNB  3
#define PRO_TYPE_UAV  4
#define PRO_TYPE_FMAC 5
#define PRO_TYPE_IOT 6
#define PRO_TYPE_FPV  7

#define PRO_TYPE_QA   66
#define PRO_TYPE_QC   88


#ifdef TXW4002ACK803
#include "txw4002ack803/txw4002ack803.h"
#include "txw4002ack803/io_function.h"
#include "txw4002ack803/pin_names.h"
#include "txw4002ack803/sysctrl.h"
#include "txw4002ack803/test_atcmd.h"
#endif

#ifdef TXW80X
#include "txw80x/txw80x.h"
#include "txw80x/pin_names.h"
#include "txw80x/io_function.h"
#include "txw80x/adc_voltage_type.h"
#include "txw80x/sysctrl.h"
#include "txw80x/pmu.h"
#include "txw80x/misc.h"
#include "txw80x/boot_lib.h"
#endif


#endif
