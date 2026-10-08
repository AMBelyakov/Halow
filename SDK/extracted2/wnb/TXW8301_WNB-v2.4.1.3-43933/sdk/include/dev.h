#ifndef _HUGEIC_DEV_H_
#define _HUGEIC_DEV_H_

#ifdef __cplusplus
extern "C" {
#endif

struct dev_obj;

struct devobj_ops{
#ifdef CONFIG_SLEEP
    int32 (*suspend)(struct dev_obj *obj);
    int32 (*resume)(struct dev_obj *obj);
#endif
};

struct dev_obj{
    uint32 dev_id;
    struct dev_obj *next;
    const struct devobj_ops *ops;
};

/**
 * dev core module initialize
 * @return return RET_OK if initialize sucess, else return RET_ERR.
 **/
extern int32 dev_init(void);

/**
 * get dev by dev_id
 * @param[in] dev_id device id
 * @return return device object if device exist, else return NULL.
 **/
extern struct dev_obj *dev_get(int32 dev_id);

/**
 * register device into dev manager.
 * @param[in] device object to register.
 * @return return RET_OK if register sucess, else return RET_ERR.
 **/
extern int32 dev_register(uint32 dev_id, struct dev_obj *device);

#ifdef CONFIG_SLEEP
/**
 * device suspend when system enter sleep.
 * @param[in] dsleep sleep or deep sleep.
 * @return return RET_OK if unregister sucess, else return RET_ERR.
 **/
extern int32 dev_suspend(uint16 type);
extern int32 dev_suspend_hook(struct dev_obj *dev, uint16 type);

/**
 * device resume when system resume.
 * @return return RET_OK if unregister sucess, else return RET_ERR.
 **/
extern int32 dev_resume(uint16 type, uint32 wkreason);
extern int32 dev_resume_hook(struct dev_obj *dev, uint16 type, uint32 wkreason);
#endif

extern int32 pin_func(int32 dev_id, int32 request);

#ifdef __cplusplus
}
#endif

#endif
