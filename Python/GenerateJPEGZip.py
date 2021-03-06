import numpy as n
import os
import os.path
from PIL import Image
import sys
from zipfile import ZipFile, ZIP_STORED
import zipfile
import cPickle as pickle
from StringIO import StringIO
from time import time
import itertools


# process the folder datadir
# with subfolder names inside the id2label keys
# process only labelnum of labels
def process(perm, id2label, datadir, labelnum, batchsize, stordir, base=0):

    # 1. read all the images and corresponding labels under this folder
    images = []
    labels = []
    for label, dirs in zip(range(len(perm)), perm):
        if label >= labelnum:
            break
        for img in os.listdir(os.path.join(datadir, dirs)):
            labels.append(label)
            images.append(os.path.join(datadir, dirs, img))

    # 2. randperm the images and labels
    rarray = n.random.permutation(range(len(labels)))
    num = len(labels)/batchsize
    totalnum = num
    if len(labels) % batchsize is not 0:
        totalnum = num+1

    # Split them into batches
    label_batches = []
    image_batches = []
    for i in range(num):
        sublabels = []
        filenames = []
        for idx in rarray[i*batchsize:(i+1)*batchsize]:
            sublabels.append(labels[idx])
            filenames.append(images[idx])
        label_batches.append(sublabels)
        image_batches.append(filenames)

    if totalnum > num: # still some left
        sublabels = []
        filenames = []
        for idx in rarray[num*batchsize:]:
            sublabels.append(labels[idx])
            filenames.append(images[idx])
        label_batches.append(sublabels)
        image_batches.append(filenames)

    # meta
    dic = {'batch_idx': range(totalnum), 'label_batches': label_batches, 'image_batches': image_batches}

    # zip images
    for i in dic['batch_idx']:
        zipfilename = os.path.join(stordir, 'data_batch_'+str(base+i+1))
        myzip = ZipFile(zipfilename, 'w', zipfile.ZIP_STORED)
        newstaff = []
        for img in dic['image_batches'][i]:
            myzip.write(img, os.path.basename(img))
            newstaff.append(os.path.basename(img))
        dic['image_batches'][i] = newstaff
        myzip.close()

    return dic

def calcMean(datadir, r, dimData):
    sumlist = []
    meta = {}
    totalnum = 0
    subdirs = os.listdir(datadir)
    for idx in r:
        # t0 = time()
        f = open(os.path.join(datadir, 'data_batch_'+str(idx)), 'r')
        memfile = StringIO(f.read())
        f.close()
        zipf = zipfile.ZipFile(memfile, 'r', ZIP_STORED)
        # get the file list from meta
        filelist = zipf.namelist()
        totalnum += len(filelist)
        data = n.zeros((len(filelist), dimData), dtype=n.float32)
        for i in range(len(filelist)):
            arr = n.array(Image.open(StringIO(zipf.read(filelist[i]))))
            if arr.ndim == 3:
                data[i, :] = n.concatenate([arr[:,:,0].flatten('C'), arr[:,:,1].flatten('C'), arr[:,:,2].flatten('C')])
            else:
                data[i, :] = arr.flatten('C')

	# print time()-t0
        # data = n.array(data)
        s = n.sum(data, axis=0)
        sumlist.append(s)

    # assert(len(sumlist)==(len(subdirs)-1))
    # assert(totalnum==1281167) # the number of imagenet training images

    sumlist = n.array(sumlist)
    allsum = n.sum(sumlist, axis=0)
    mean = n.divide(allsum, totalnum)
    mean = n.require(mean.T, n.float32, 'C')
    mean = mean.reshape(mean.size, 1)
    return mean


if __name__ == "__main__":

    # Let's randomly permute the labels here
    # First get the ID2Label mapping.
    # map each of the foldeer to a number
    datadir = sys.argv[1]
    stordir = sys.argv[2]
    imgSize  = int(sys.argv[3])
    channels = int(sys.argv[4])

    dimData = channels * imgSize**2
    batchSize = int(sys.argv[5])

    # Read in all the Id 2 label Information
    ID2Label = open(os.path.join(datadir, 'ID2Label'))
    id2label = {}
    for line in ID2Label:
        (foldername, labelname) = line.split('|')
        id2label[foldername.strip()]=labelname.strip().replace('\r\n','')

    # process imagenet
    labelnum = int(sys.argv[6])

    # permute the id 2 label
    perm = n.random.permutation(id2label.keys())

    # Get the label names in the permutation order
    labelnames = []
    for item in perm:
        labelnames.append(id2label[item])
    labelnames = labelnames[:labelnum]

    # process train and test
    train = process(perm, id2label, os.path.join(datadir, 'train'), labelnum, batchSize, stordir, 0)
    trainidxnum = len(train['batch_idx'])
    test  = process(perm, id2label, os.path.join(datadir, 'test'),  labelnum, batchSize, stordir, trainidxnum)

    # merge meta
    for i in range(len(test['batch_idx'])):
        test['batch_idx'][i] += trainidxnum

    dic = {'data_name': datadir, 'num_colors': channels, 'batch_size': batchSize, 'num_vis': channels * imgSize**2, 'image_size': imgSize}
    dic['batch_idx'] = train['batch_idx'] + test['batch_idx']

    for i in range(len(dic['batch_idx'])):
        dic['batch_idx'][i] += 1

    dic['label_batches'] = train['label_batches'] + test['label_batches']
    dic['image_batches'] = train['image_batches'] + test['image_batches']
    
    print 'training batches: 1-'+str(trainidxnum)

    # calcmean
    mean = calcMean(stordir, range(1, trainidxnum+1), dimData)
    dic['data_mean'] = mean
    dic['num_cases_per_batch'] = batchSize
    dic['label_names'] = labelnames
    
    # dump meta
    pickle.dump(dic,open(os.path.join(stordir, 'batches.meta'),'w'))

    
