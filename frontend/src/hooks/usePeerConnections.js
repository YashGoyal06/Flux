import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import server from '../environment';

const turnServerUrl = process.env.REACT_APP_TURN_SERVER_URL || 'turn:openrelay.metered.ca:443';
const turnServerUsername = process.env.REACT_APP_TURN_SERVER_USERNAME || 'openrelayproject';
const turnServerCredential = process.env.REACT_APP_TURN_SERVER_PASSWORD || 'openrelayproject';

const peerConfig = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' },
        { urls: 'stun:stun3.l.google.com:19302' },
        { urls: 'stun:stun4.l.google.com:19302' },
        {
            urls: turnServerUrl,
            username: turnServerUsername,
            credential: turnServerCredential
        },
        {
            urls: 'turn:openrelay.metered.ca:80',
            username: 'openrelayproject',
            credential: 'openrelayproject'
        }
    ],
    iceCandidatePoolSize: 10,
};

const websocketUrlForRoom = (roomCode) => {
    const baseUrl = new URL(server);
    baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    baseUrl.pathname = `/ws/call/${roomCode}/`;
    baseUrl.search = '';
    baseUrl.hash = '';
    return baseUrl.toString();
};

export const usePeerConnections = (roomCode, username, localStream) => {
    const [videoStreams, setVideoStreams] = useState([]);
    const [connectionError, setConnectionError] = useState(null);
    const [socketState, setSocketState] = useState(null);
    const [peerConnectionState, setPeerConnectionState] = useState({});

    const socketRef = useRef(null);
    const socketIdRef = useRef(null);
    const listenersRef = useRef({});
    const peerConnectionsRef = useRef({});
    const pendingCandidatesRef = useRef({});
    const participantNamesRef = useRef({});
    const remoteStreamsRef = useRef({});
    const localStreamRef = useRef(localStream);

    const sendSocketEvent = useCallback((payload) => {
        const socket = socketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        socket.send(JSON.stringify(payload));
    }, []);

    const notifySocketListeners = useCallback((event, ...args) => {
        (listenersRef.current[event] || []).forEach((listener) => listener(...args));
    }, []);

    const upsertVideoStream = useCallback((streamData) => {
        setVideoStreams((prev) => {
            const existingIndex = prev.findIndex((item) => (
                item.socketId === streamData.socketId && item.type === streamData.type
            ));

            if (existingIndex === -1) {
                return [...prev, streamData];
            }

            const next = [...prev];
            next[existingIndex] = { ...next[existingIndex], ...streamData, timestamp: Date.now() };
            return next;
        });
    }, []);

    const removePeer = useCallback((socketId) => {
        if (peerConnectionsRef.current[socketId]) {
            peerConnectionsRef.current[socketId].close();
            delete peerConnectionsRef.current[socketId];
        }

        delete pendingCandidatesRef.current[socketId];
        delete participantNamesRef.current[socketId];
        delete remoteStreamsRef.current[socketId];

        setPeerConnectionState({ ...peerConnectionsRef.current });
        setVideoStreams((prev) => prev.filter((item) => item.socketId !== socketId));
    }, []);

    useEffect(() => {
        localStreamRef.current = localStream;

        if (!localStream || !socketIdRef.current) return;

        upsertVideoStream({
            socketId: socketIdRef.current,
            stream: localStream,
            type: 'camera',
            name: username,
            isLocal: true,
            timestamp: Date.now(),
        });

        Object.values(peerConnectionsRef.current).forEach((peerConnection) => {
            const senders = peerConnection.getSenders();

            localStream.getTracks().forEach((track) => {
                const sender = senders.find((item) => item.track?.kind === track.kind);
                if (sender) {
                    sender.replaceTrack(track).catch((error) => {
                        console.warn('Could not replace local track:', error);
                    });
                } else {
                    peerConnection.addTrack(track, localStream);
                }
            });
        });
    }, [localStream, upsertVideoStream, username]);

    const createPeerConnection = useCallback((socketId) => {
        if (peerConnectionsRef.current[socketId]) {
            return peerConnectionsRef.current[socketId];
        }

        const peerConnection = new RTCPeerConnection(peerConfig);
        peerConnectionsRef.current[socketId] = peerConnection;
        remoteStreamsRef.current[socketId] = [];
        setPeerConnectionState({ ...peerConnectionsRef.current });

        if (localStreamRef.current) {
            localStreamRef.current.getTracks().forEach((track) => {
                peerConnection.addTrack(track, localStreamRef.current);
            });
        }

        peerConnection.onicecandidate = (event) => {
            if (!event.candidate) return;
            sendSocketEvent({
                event: 'signal',
                toId: socketId,
                message: JSON.stringify({ ice: event.candidate }),
            });
        };

        peerConnection.ontrack = (event) => {
            const [remoteStream] = event.streams;
            if (!remoteStream) return;

            const knownStreams = remoteStreamsRef.current[socketId] || [];
            const streamIndex = knownStreams.findIndex((stream) => stream.id === remoteStream.id);

            if (streamIndex === -1) {
                knownStreams.push(remoteStream);
                remoteStreamsRef.current[socketId] = knownStreams;
            }

            const currentIndex = streamIndex === -1 ? knownStreams.length - 1 : streamIndex;
            const type = currentIndex === 0 ? 'camera' : 'screen';
            const name = participantNamesRef.current[socketId] || 'Guest';

            upsertVideoStream({
                socketId,
                stream: remoteStream,
                type,
                name: type === 'screen' ? `${name}'s Screen` : name,
                isLocal: false,
                timestamp: Date.now(),
            });

            remoteStream.getTracks().forEach((track) => {
                track.onended = () => {
                    if (remoteStream.getTracks().every((item) => item.readyState === 'ended')) {
                        setVideoStreams((prev) => prev.filter((item) => (
                            !(item.socketId === socketId && item.stream.id === remoteStream.id)
                        )));
                    }
                };
            });
        };

        peerConnection.onconnectionstatechange = () => {
            if (['failed', 'closed'].includes(peerConnection.connectionState)) {
                removePeer(socketId);
            }
        };

        return peerConnection;
    }, [removePeer, sendSocketEvent, upsertVideoStream]);

    const flushPendingCandidates = useCallback(async (socketId) => {
        const peerConnection = peerConnectionsRef.current[socketId];
        const pendingCandidates = pendingCandidatesRef.current[socketId] || [];

        if (!peerConnection?.remoteDescription || pendingCandidates.length === 0) return;

        for (const candidate of pendingCandidates) {
            try {
                await peerConnection.addIceCandidate(candidate);
            } catch (error) {
                console.warn('Could not add queued ICE candidate:', error);
            }
        }

        delete pendingCandidatesRef.current[socketId];
    }, []);

    const makeOffer = useCallback(async (socketId) => {
        const peerConnection = createPeerConnection(socketId);

        if (peerConnection.signalingState !== 'stable') return;

        const offer = await peerConnection.createOffer({
            offerToReceiveAudio: true,
            offerToReceiveVideo: true,
        });

        await peerConnection.setLocalDescription(offer);
        sendSocketEvent({
            event: 'signal',
            toId: socketId,
            message: JSON.stringify({ sdp: peerConnection.localDescription }),
        });
    }, [createPeerConnection, sendSocketEvent]);

    const handleSignal = useCallback(async (fromSocketId, message) => {
        let signal;

        try {
            signal = JSON.parse(message);
        } catch (error) {
            console.warn('Ignoring invalid signaling payload:', error);
            return;
        }

        const peerConnection = createPeerConnection(fromSocketId);

        try {
            if (signal.sdp) {
                const description = new RTCSessionDescription(signal.sdp);

                if (description.type === 'offer') {
                    if (peerConnection.signalingState !== 'stable') {
                        await peerConnection.setLocalDescription({ type: 'rollback' });
                    }

                    await peerConnection.setRemoteDescription(description);
                    await flushPendingCandidates(fromSocketId);

                    const answer = await peerConnection.createAnswer();
                    await peerConnection.setLocalDescription(answer);
                    sendSocketEvent({
                        event: 'signal',
                        toId: fromSocketId,
                        message: JSON.stringify({ sdp: peerConnection.localDescription }),
                    });
                    return;
                }

                if (description.type === 'answer' && peerConnection.signalingState === 'have-local-offer') {
                    await peerConnection.setRemoteDescription(description);
                    await flushPendingCandidates(fromSocketId);
                }
            }

            if (signal.ice) {
                const candidate = new RTCIceCandidate(signal.ice);

                if (peerConnection.remoteDescription) {
                    await peerConnection.addIceCandidate(candidate);
                } else {
                    pendingCandidatesRef.current[fromSocketId] = [
                        ...(pendingCandidatesRef.current[fromSocketId] || []),
                        candidate,
                    ];
                }
            }
        } catch (error) {
            console.error('Signaling failed:', error);
            setConnectionError(error.message);
        }
    }, [createPeerConnection, flushPendingCandidates, sendSocketEvent]);

    const updateParticipantName = useCallback((socketId, name) => {
        if (!socketId || !name) return;

        participantNamesRef.current[socketId] = name;
        setVideoStreams((prev) => prev.map((item) => {
            if (item.socketId !== socketId || item.isLocal) return item;
            return {
                ...item,
                name: item.type === 'screen' ? `${name}'s Screen` : name,
            };
        }));
    }, []);

    const handleSocketMessage = useCallback(async (rawMessage) => {
        const payload = JSON.parse(rawMessage.data);

        switch (payload.event) {
            case 'connect':
                socketIdRef.current = payload.socketId;
                upsertVideoStream({
                    socketId: payload.socketId,
                    stream: localStreamRef.current,
                    type: 'camera',
                    name: username,
                    isLocal: true,
                    timestamp: Date.now(),
                });
                sendSocketEvent({ event: 'username', username });
                sendSocketEvent({ event: 'join-call' });
                break;

            case 'room-users':
                for (const user of payload.users || []) {
                    updateParticipantName(user.socketId, user.username);
                    await makeOffer(user.socketId);
                }
                break;

            case 'user-joined':
                updateParticipantName(payload.user?.socketId, payload.user?.username);
                break;

            case 'username':
                updateParticipantName(payload.socketId, payload.username);
                break;

            case 'signal':
                await handleSignal(payload.fromSocketId, payload.message);
                break;

            case 'chat-message':
                notifySocketListeners(
                    'chat-message',
                    payload.data,
                    payload.sender,
                    payload.socketIdSender,
                );
                break;

            case 'user-left':
                removePeer(payload.socketId);
                break;

            case 'screen-share-stopped':
                setVideoStreams((prev) => prev.filter((item) => (
                    !(item.socketId === payload.sharerSocketId && item.type === 'screen')
                )));
                break;

            default:
                break;
        }
    }, [
        handleSignal,
        makeOffer,
        notifySocketListeners,
        removePeer,
        sendSocketEvent,
        updateParticipantName,
        upsertVideoStream,
        username,
    ]);

    useEffect(() => {
        if (!roomCode || !username || !localStream) return;
        if (socketRef.current) return;

        const socket = new WebSocket(websocketUrlForRoom(roomCode));
        socketRef.current = socket;
        setSocketState({
            emit: (event, ...args) => {
                if (event === 'signal') {
                    sendSocketEvent({ event, toId: args[0], message: args[1] });
                }

                if (event === 'chat-message') {
                    sendSocketEvent({ event, data: args[0], sender: args[1] });
                }

                if (event === 'screen-share-started' || event === 'screen-share-stopped') {
                    sendSocketEvent({ event, sharerSocketId: socketIdRef.current });
                }
            },
            on: (event, listener) => {
                listenersRef.current[event] = [
                    ...(listenersRef.current[event] || []),
                    listener,
                ];
            },
            off: (event, listener) => {
                listenersRef.current[event] = (listenersRef.current[event] || [])
                    .filter((item) => item !== listener);
            },
            disconnect: () => socket.close(),
            get id() {
                return socketIdRef.current;
            },
        });

        socket.onopen = () => setConnectionError(null);
        socket.onmessage = handleSocketMessage;
        socket.onerror = () => setConnectionError('WebSocket connection failed');
        socket.onclose = () => {
            if (socketRef.current === socket) {
                setConnectionError('Disconnected from call server');
            }
        };

        return () => {
            Object.values(peerConnectionsRef.current).forEach((peerConnection) => peerConnection.close());
            peerConnectionsRef.current = {};
            pendingCandidatesRef.current = {};
            participantNamesRef.current = {};
            remoteStreamsRef.current = {};
            listenersRef.current = {};
            socketIdRef.current = null;

            socket.close();
            socketRef.current = null;
            setSocketState(null);
            setPeerConnectionState({});
        };
    }, [handleSocketMessage, localStream, roomCode, sendSocketEvent, username]);

    return useMemo(() => ({
        videoStreams,
        connectionError,
        socket: socketState,
        peerConnections: peerConnectionState,
    }), [connectionError, peerConnectionState, socketState, videoStreams]);
};
