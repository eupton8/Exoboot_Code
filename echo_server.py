import socket  # Import socket module
import numpy as np
import matplotlib.pyplot as plt
#matplotlib.use('TKagg')
#print(matplotlib.get_backend())
#import matplotlib.pyplot as plt

#import time
#from matplotlib import pyplot
#from matplotlib.animation import FuncAnimation
global parsedData

plt.ion()
fig=plt.figure()
#x_data, y_data = [], []
#line = pyplot.plot_date(x_data, y_data, '-')

port = 50000  # Reserve a port for your service every new transfer wants a new port or you must wait.
s = socket.socket()  # Create a socket object
host = ""  # Get local machine name
s.bind(('localhost', port))  # Bind to the port
s.listen(5)  # Now wait for client connection.
    
print('Server listening....')
    
x = 1
dataBuffer=[0]
counter=0

while True:
    conn, address = s.accept()  # Establish connection with client.
    
    while True:
        try:
            #print('Got connection from', address)
            data = conn.recv(1024)

            newData=data.decode()
            for k in range(len(newData)):
                if newData[k]==".":
                    parsedData=newData[:k+3]
                    break
                else:
                    parsedData=newData
            
            print(parsedData)
            #print('Server received ', data.decode())
            #if type(float(data.decode()))== float:
            '''
                counter+=1
                dataBuffer.append(float(data.decode()))
                
                if counter>9:
                    plt.plot(dataBuffer[-9:])
                    #dataBuffer.clear()
                    counter=0
                    plt.show()
                    plt.pause(0.0001)
            '''
            plt.scatter(x,float(parsedData))
            ##plt.plot(x,parsedData,'b-')
            plt.show()
            plt.pause(0.0001)
            
            #plt.show()
	    #st = 'Thank you for connecting'
            #byt = st.encode()
            #conn.send(byt)
    
            x += 1
        except Exception as e:
            print(e)
            break
    
conn.close()
