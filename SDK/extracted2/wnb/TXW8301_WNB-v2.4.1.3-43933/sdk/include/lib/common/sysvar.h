
#ifndef _HGIC_SYSVAR_H_
#define _HGIC_SYSVAR_H_
enum sysvar_id {
    SYSVAR_ID_LMACHOST,
    SYSVAR_ID_ATCMD_MGR,
    SYSVAR_ID_IEEE80211_HW,
    SYSVAR_ID_WIFIMGR,
    SYSVAR_ID_SYSEVT,
    SYSVAR_ID_MAX,
};

#ifdef ROMCODE_EN
extern const uint32 sys_vector[];
#define sysvar(id, size) ((void * (*)(int, int))sys_vector[2])(id, size)
#else
void *sysvar(enum sysvar_id id, int size);
#endif
#endif
