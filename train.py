#coding:utf-8
import tensorflow as tf
import numpy as np
import os
from datetime import datetime
import sys
sys.path.append("../prepare_data")
from read_tfrecord_v2 import read_multi_tfrecords,read_single_tfrecord
from MTCNN_config import config
from mtcnn_model import P_Net
import random
import numpy.random as npr
import cv2

train_face = config.train_face

def train_model(base_lr, loss, data_num):
    """
    train model
    :param base_lr: base learning rate
    :param loss: loss
    :param data_num:
    :return:
    train_op, lr_op
    """
    lr_factor = 0.1
    global_step = tf.Variable(0, trainable=False)
    #LR_EPOCH [8,14]
    #boundaried [num_batch,num_batch]
    boundaries = [int(epoch * data_num / config.BATCH_SIZE) for epoch in config.LR_EPOCH]
    print("boundaries ",boundaries)
    #lr_values[0.01,0.001,0.0001,0.00001]
    lr_values = [base_lr * (lr_factor ** x) for x in range(0, len(config.LR_EPOCH) + 1)]
    print("learningrate ",lr_values)
    #control learning rate
    lr_op = tf.train.piecewise_constant(global_step, boundaries, lr_values)
    optimizer = tf.train.MomentumOptimizer(lr_op, 0.9)
    train_op = optimizer.minimize(loss, global_step)

    return train_op, lr_op
'''
certain samples mirror
def random_flip_images(image_batch,label_batch,landmark_batch):
    num_images = image_batch.shape[0]
    random_number = npr.choice([0,1],num_images,replace=True)
    #the index of image needed to flip
    indexes = np.where(random_number>0)[0]
    fliplandmarkindexes = np.where(label_batch[indexes]==-2)[0]

    #random flip
    for i in indexes:
        cv2.flip(image_batch[i],1,image_batch[i])
    #pay attention: flip landmark
    for i in fliplandmarkindexes:
        landmark_ = landmark_batch[i].reshape((-1,2))
        landmark_ = np.asarray([(1-x, y) for (x, y) in landmark_])
        landmark_[[0, 1]] = landmark_[[1, 0]]#left eye<->right eye
        landmark_[[3, 4]] = landmark_[[4, 3]]#left mouth<->right mouth
        landmark_batch[i] = landmark_.ravel()
    return image_batch,landmark_batch
'''
# all mini-batch mirror
def random_flip_images(image_batch,label_batch,landmark_batch):
    #mirror
    if random.choice([0,1]) > 0:
        num_images = image_batch.shape[0]
        fliplandmarkindexes = np.where(label_batch==-2)[0]
        flipposindexes = np.where(label_batch==1)[0]
        #only flip
        flipindexes = np.concatenate((fliplandmarkindexes,flipposindexes))
        #random flip
        for i in flipindexes:
            cv2.flip(image_batch[i],1,image_batch[i])

        #pay attention: flip landmark
        for i in fliplandmarkindexes:
            landmark_ = landmark_batch[i].reshape((-1,2))
            landmark_ = np.asarray([(1-x, y) for (x, y) in landmark_])
            landmark_[[0, 1]] = landmark_[[1, 0]]#left eye<->right eye
            landmark_[[3, 4]] = landmark_[[4, 3]]#left mouth<->right mouth
            landmark_batch[i] = landmark_.ravel()

    return image_batch,landmark_batch

def train(net_factory, prefix,load_epoch, end_epoch, base_dir,
          display=200, base_lr=0.01,gpu_ctx='/device:GPU:0'):
    """
    train PNet/RNet/ONet
    :param net_factory:
    :param prefix:
    :param end_epoch:16
    :param dataset:
    :param display:
    :param base_lr:
    :return:
    """
    net = prefix.split('/')[-1]
    #label file
    label_file = os.path.join(base_dir,'train_%s_landmark.txt' % net)
    #label_file = os.path.join(base_dir,'landmark_12_few.txt')
    #print label_file
    f = open(label_file, 'r')
    num = len(f.readlines())
    print("Total datasets is: ", num)
    print( "saved prefix: ",prefix)

    #PNet use this method to get data
    if net == 'PNet':
        #dataset_dir = os.path.join(base_dir,'train_%s_ALL.tfrecord_shuffle' % net)
        dataset_dir = os.path.join(base_dir,'train_%s_landmark.tfrecord_shuffle' % net)
        print("dataset saved dir: ",dataset_dir)
        image_batch, label_batch, bbox_batch,landmark_batch = read_single_tfrecord(dataset_dir, config.BATCH_SIZE, net)

    #RNet use 3 tfrecords to get data
    else:
        pos_dir = os.path.join(base_dir,'pos_landmark.tfrecord_shuffle')
        part_dir = os.path.join(base_dir,'part_landmark.tfrecord_shuffle')
        neg_dir = os.path.join(base_dir,'neg_landmark.tfrecord_shuffle')
        if train_face:
            landmark_dir = os.path.join(base_dir,'landmark_landmark.tfrecord_shuffle')
        else:
            landmark_dir = None
        dataset_dirs = [pos_dir,part_dir,neg_dir,landmark_dir]
        if train_face:
            pos_radio = 1.0/6;part_radio = 1.0/6;landmark_radio=1.0/6;neg_radio=3.0/6
        else:
            pos_radio = 2.0/3;part_radio = 1.0/6;landmark_radio=0
        pos_batch_size = int(np.ceil(config.BATCH_SIZE*pos_radio))
        assert pos_batch_size != 0,"Batch Size Error "
        part_batch_size = int(np.ceil(config.BATCH_SIZE*part_radio))
        assert part_batch_size != 0,"Batch Size Error "
        if train_face:
            neg_batch_size = int(np.ceil(config.BATCH_SIZE*neg_radio))
            assert neg_batch_size != 0,"Batch Size Error "
            #landmark_batch_size = int(np.ceil(config.BATCH_SIZE*landmark_radio))
            landmark_batch_size = int(config.BATCH_SIZE-pos_batch_size-part_batch_size-neg_batch_size)
            assert landmark_batch_size != 0,"Batch Size Error "
            batch_sizes = [pos_batch_size,part_batch_size,neg_batch_size,landmark_batch_size]
            image_batch, label_batch, bbox_batch,landmark_batch = read_multi_tfrecords(dataset_dirs,batch_sizes, net)
        else:
            landmark_batch_size = 1
            neg_batch_size = int(config.BATCH_SIZE-pos_batch_size-part_batch_size)
            assert neg_batch_size != 0,"Batch Size Error "
            batch_sizes = [pos_batch_size,part_batch_size,neg_batch_size,landmark_batch_size]
            image_batch, label_batch, bbox_batch = read_multi_tfrecords(dataset_dirs,batch_sizes, net)

    #landmark_dir
    if net == 'PNet':
        image_size = 12
        radio_cls_loss = 1.0;radio_bbox_loss = 0.5;radio_landmark_loss = 0.5
    elif net == 'RNet':
        image_size = 24
        #radio_cls_loss = 1.0;radio_bbox_loss = 0.5;radio_landmark_loss = 0.5
        radio_cls_loss = 1.0;radio_bbox_loss = 0.5;radio_landmark_loss = 1.0
    else:
        radio_cls_loss = 1.0;radio_bbox_loss = 0.5;radio_landmark_loss = 1.0
        image_size = 48

    #define placeholder
    input_image = tf.placeholder(tf.float32, shape=[config.BATCH_SIZE, image_size, image_size, 3], name='input_image')
    label = tf.placeholder(tf.float32, shape=[config.BATCH_SIZE], name='label')
    bbox_target = tf.placeholder(tf.float32, shape=[config.BATCH_SIZE, 4], name='bbox_target')
    landmark_target = tf.placeholder(tf.float32,shape=[config.BATCH_SIZE,10],name='landmark_target')
    #class,regression
    #with tf.device(gpu_ctx):
    if train_face :
        cls_loss_op,bbox_loss_op,landmark_loss_op,L2_loss_op,accuracy_op = net_factory(input_image, label, bbox_target,landmark_target,training=True)
    else:
        cls_loss_op,bbox_loss_op,landmark_loss_op,L2_loss_op,accuracy_op = net_factory(input_image, label, bbox_target,training=True)
    #train,update learning rate(3 loss)
    train_op, lr_op = train_model(base_lr, radio_cls_loss*cls_loss_op + radio_bbox_loss*bbox_loss_op + radio_landmark_loss*landmark_loss_op + L2_loss_op, num)
    # init
    #init = tf.global_variables_initializer()
    #gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.7)
    #tf_config.gpu_options = gpu_options
    tf_config = tf.ConfigProto()
    tf_config.gpu_options.allow_growth=True  
    tf_config.log_device_placement=False
    sess = tf.Session(config=tf_config)
    #sess = tf.Session(config=tf.ConfigProto(log_device_placement=False))
    #save model
    saver = tf.train.Saver(max_to_keep=0)
    #sess.run(init)
    #load pretrained parameters
    if load_epoch:
        #check whether the dictionary is valid
        model_path = "%s-%s" %(prefix,str(load_epoch) )
        model_dict = '/'.join(model_path.split('/')[:-1])
        ckpt = tf.train.get_checkpoint_state(model_dict)
        print("restore model path:",model_path)
        readstate = ckpt and ckpt.model_checkpoint_path
        #assert  readstate, "the params dictionary is not valid"
        saver.restore(sess, model_path)
        print("restore models' param")
    else:
        init = tf.global_variables_initializer()
        sess.run(init)
        print("init models using gloable: init")

    #visualize some variables
    tf.summary.scalar("cls_loss",cls_loss_op)#cls_loss
    tf.summary.scalar("bbox_loss",bbox_loss_op)#bbox_loss
    tf.summary.scalar("landmark_loss",landmark_loss_op)#landmark_loss
    tf.summary.scalar("cls_accuracy",accuracy_op)#cls_acc
    summary_op = tf.summary.merge_all()
    logs_dir = "../logs/%s" %(net)
    if os.path.exists(logs_dir) == False:
        os.mkdir(logs_dir)
    writer = tf.summary.FileWriter(logs_dir,sess.graph)
    #begin
    coord = tf.train.Coordinator()
    #begin enqueue thread
    threads = tf.train.start_queue_runners(sess=sess, coord=coord)
    i = 0
    #total steps
    MAX_STEP = int(num / config.BATCH_SIZE + 1) * end_epoch
    epoch = 0
    sess.graph.finalize()
    save_acc = 0
    L2_loss = 0
    model_dict = '/'.join(prefix.split('/')[:-1])
    log_r_file = os.path.join(model_dict,"train_record.txt")
    print("model record is ",log_r_file)
    record_file_out = open(log_r_file,'w')
    #record_file_out = open("train_record.txt",'w')
    try:
        for step in range(MAX_STEP):
            i = i + 1
            if coord.should_stop():
                break
            if train_face:
                if net == 'PNet':
                    image_batch_array, label_batch_array, bbox_batch_array = sess.run([image_batch, label_batch, bbox_batch])
                else:
                    image_batch_array, label_batch_array, bbox_batch_array,landmark_batch_array = sess.run([image_batch, label_batch, bbox_batch,landmark_batch])
            else:
                image_batch_array, label_batch_array, bbox_batch_array = sess.run([image_batch, label_batch, bbox_batch])
            #print("shape:  ",i, np.shape(image_batch_array),np.shape(label_batch_array),np.shape(bbox_batch_array))
            #random flip
            if train_face and not (net == 'PNet'):
                image_batch_array,landmark_batch_array = random_flip_images(image_batch_array,label_batch_array,landmark_batch_array)
            '''
            print image_batch_array.shape
            print label_batch_array.shape
            print bbox_batch_array.shape
            print landmark_batch_array.shape
            print label_batch_array[0]
            print bbox_batch_array[0]
            print landmark_batch_array[0]
            '''
            if train_face and not (net == 'PNet') :
                _,_,summary = sess.run([train_op, lr_op ,summary_op], feed_dict={input_image: image_batch_array, label: label_batch_array, bbox_target: bbox_batch_array,landmark_target:landmark_batch_array})
            else:
                _,_,summary = sess.run([train_op, lr_op ,summary_op], feed_dict={input_image: image_batch_array, label: label_batch_array, bbox_target: bbox_batch_array})
            
            if (step+1) % display == 0:
                #acc = accuracy(cls_pred, labels_batch)
                if train_face and not(net == 'PNet'):
                    cls_loss, bbox_loss,landmark_loss,L2_loss,lr,acc = sess.run([cls_loss_op, bbox_loss_op,landmark_loss_op,L2_loss_op,lr_op,accuracy_op],\
                                                             feed_dict={input_image: image_batch_array, label: label_batch_array, bbox_target: bbox_batch_array, landmark_target: landmark_batch_array})
                    print("%s : Step: %d, accuracy: %3f, cls loss: %4f, bbox loss: %4f, landmark loss: %4f,L2 loss: %4f,lr:%f " % (
                    datetime.now(), step+1, acc, cls_loss, bbox_loss, landmark_loss, L2_loss, lr))
                else:
                    cls_loss, bbox_loss,L2_loss,lr,acc = sess.run([cls_loss_op, bbox_loss_op,L2_loss_op,lr_op,accuracy_op],\
                                                             feed_dict={input_image: image_batch_array, label: label_batch_array, bbox_target: bbox_batch_array})
                    print("%s : Step: %d, accuracy: %3f, cls loss: %4f, bbox loss: %4f, L2 loss: %4f,lr:%f " % (
                    datetime.now(), step+1, acc, cls_loss, bbox_loss,L2_loss, lr))
            #save every two epochs
            if i * config.BATCH_SIZE > num*10:
                epoch = epoch + 1
                i = 0
                #if save_acc < L2_loss:
                saver.save(sess, prefix, global_step=epoch*100)
                save_acc = L2_loss
                if train_face and not (net == 'PNet'):
                    print("%s : Step: %d, accuracy: %3f, cls loss: %4f, bbox loss: %4f, landmark loss: %4f,L2 loss: %4f,lr:%f " % (datetime.now(), step+1, acc, cls_loss, bbox_loss,landmark_loss,L2_loss, lr))
                    record_file_out.write("%s : epoch: %d, accuracy: %3f, cls loss: %4f, bbox loss: %4f, landmark_loss: %4f,lr:%f \n" % (datetime.now(), epoch*100, acc, cls_loss, bbox_loss,landmark_loss, lr))
                else:
                    print("%s : Step: %d, accuracy: %3f, cls loss: %4f, bbox loss: %4f, L2 loss: %4f,lr:%f " % (datetime.now(), step+1, acc, cls_loss, bbox_loss,L2_loss, lr))
                    record_file_out.write("%s : epoch: %d, accuracy: %3f, cls loss: %4f, bbox loss: %4f, L2_loss: %4f,lr:%f \n" % (datetime.now(), epoch*100, acc, cls_loss, bbox_loss,L2_loss, lr))
                print("model saved over ",save_acc)
            writer.add_summary(summary,global_step=step)
    except tf.errors.OutOfRangeError:
        print("Over！！！")
    finally:
        coord.request_stop()
        writer.close()
    coord.join(threads)
    record_file_out.close()
    sess.close()
