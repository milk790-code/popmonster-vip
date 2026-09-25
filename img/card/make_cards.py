import numpy as np, os, re, glob, sys
from PIL import Image, ImageFilter
def to_lin(a):
    a=a/255.0; return np.where(a<=0.04045, a/12.92, ((a+0.055)/1.055)**2.4)
def to_srgb(a):
    a=np.clip(a,0,1); return np.where(a<=0.0031308, a*12.92, 1.055*a**(1/2.4)-0.055)*255
def resize_linear(im, w):
    a=to_lin(np.asarray(im.convert('RGB'),dtype=np.float64))
    chans=[Image.fromarray(a[:,:,c].astype(np.float32)).resize((w,w),Image.LANCZOS) for c in range(3)]
    b=np.stack([np.asarray(c,dtype=np.float64) for c in chans],-1)
    return Image.fromarray(np.round(to_srgb(b)).astype(np.uint8))
def psnr(a,b):
    a=np.asarray(a,dtype=np.float64); b=np.asarray(b,dtype=np.float64); m=((a-b)**2).mean(); return 99 if m==0 else 10*np.log10(255**2/m)
# 來源固定寫死：只用已在網站上當主圖的實拍檔（不可從 img/card/ 自己讀回來）
REAL={'a005':'img/real/a005-shi10-studio.jpg','a008':'img/real/a008-superfoam.jpg'}
SKUS=['a001','a002','a003','a004','a005','a006','a007','a008','a010','a012','a020','a024','a030','a031','a032','a034','a035','a039','a041','a043','a044','a045','a046']
srcs=[REAL.get(s,f'img/{s}-main.jpg') for s in SKUS]
tot_src=tot_640=0; rows=[]
for s in srcs:
    im=Image.open(s).convert('RGB'); W=im.width
    sku=re.search(r'a0\d\d',s).group(0)
    for w in (640,400,160):
        if W < w: continue
        r=resize_linear(im,w)
        sh=r.filter(ImageFilter.UnsharpMask(radius=0.5,percent=20,threshold=3))
        out=f'img/card/{sku}-{w}.jpg'
        for q in (80,82,84,86,88,90,92,95):
            sh.save(out,'JPEG',quality=q,progressive=True,optimize=True,subsampling=0)
            back=Image.open(out).convert('RGB')
            if psnr(back,r) >= 37: break
        ref=r
        p=psnr(back,ref)
        # overshoot: max positive difference vs unsharpened linear resize
        ov=(np.asarray(sh,dtype=np.int16)-np.asarray(r,dtype=np.int16)).max()
        ov99=np.percentile(np.asarray(sh,dtype=np.int16)-np.asarray(r,dtype=np.int16),99.9)
        kb=os.path.getsize(out)/1024
        rows.append((out,w,round(p,1),int(ov),round(float(ov99),1),round(kb,1),'q%d'%q))
        if w==640: tot_640+=kb; tot_src+=os.path.getsize(s)/1024
for r in rows: print(*r)
print('640 total %.0f KB vs src %.0f KB = %.0f%%'%(tot_640,tot_src,100*tot_640/tot_src))
