#ifndef __ADJUSTER_H__
#define __ADJUSTER_H__

#include "usbd_cdc.h"

void ProcessReceivedData(uint8_t* data, uint32_t len);
void USB_Init(void);

#endif //__ADJUSTER_H__
